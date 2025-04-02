import express from "express";
import dotenv from "dotenv";
import process from "process";
import { OpenAI } from "openai";

dotenv.config();

const app = express();
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

const INACTIVITY_TIMEOUT =
  (process.env.INACTIVITY_TIMEOUT_MINUTE
    ? parseInt(process.env.INACTIVITY_TIMEOUT_MINUTE)
    : 3) *
  60 *
  1000;

let stopFetching = false;

// Add server identification
const serverId = process.env.SERVER_ID || "default";
const serverQueues = {};
const serverConversations = {};

// Initialize LLM client based on provider
function initializeLLMClient() {
  const provider = process.env.LLM_PROVIDER?.toLowerCase() || "openai";

  const config = {
    apiKey: process.env.LLM_API_KEY,
  };

  // Add base URL for non-OpenAI providers
  if (provider !== "openai") {
    config.baseURL = process.env.LLM_BASE_URL;
  }

  return new OpenAI(config);
}

const llmClient = initializeLLMClient();

function signalHandler(signal) {
  console.log(`Received ${signal}. Initiating graceful shutdown...`);
  cleanupBeforeExit()
    .then(() => {
      process.exit(0);
    })
    .catch((err) => {
      console.error("Error during cleanup:", err);
      process.exit(1);
    });
}

// Handle SIGINT signals for Ctrl+C
process.on("SIGINT", signalHandler);

// Handle custom signal (e.g., SIGUSR1) from frunner.sh
process.on("SIGUSR1", signalHandler);

// Handle rate limit errors
let numErr = 0;
async function handleGlobalError(serverId) {
  console.log(`Error counter for server ${serverId}: `, numErr);
  if (numErr > 5) {
    console.log(
      `Too many errors on server ${serverId}, resetting conversations`
    );
    const storage = getServerStorage(serverId);
    Object.keys(storage.conversations).forEach((chatId) => {
      closeChatSession(serverId, chatId);
    });
    numErr = 0;
  }
}

// Modify conversation storage to be server-specific
function getServerStorage(serverId) {
  if (!serverConversations[serverId]) {
    serverConversations[serverId] = {};
    serverQueues[serverId] = {};
  }
  return {
    conversations: serverConversations[serverId],
    queues: serverQueues[serverId],
  };
}

// Modified chat session management
async function closeChatSession(serverId, chatId) {
  const storage = getServerStorage(serverId);
  if (storage.conversations[chatId]) {
    console.log(`Closing chat session ${chatId} for server ${serverId}`);
    delete storage.conversations[chatId];
    delete storage.queues[chatId];
  }
}

const sequentialMiddleware = (req, res, next) => {
  const { chatId, serverId = "default" } = req.body;
  if (!chatId) {
    return res.status(400).json({ message: "Chat ID is required" });
  }

  const storage = getServerStorage(serverId);
  const entry = { req, res, next, disconnected: false };

  if (!storage.queues[chatId]) {
    storage.queues[chatId] = Promise.resolve();
  }

  storage.queues[chatId] = storage.queues[chatId].then(() =>
    processRequest(entry)
  );

  res.on("close", () => {
    console.log(
      `Client disconnected from chat ${chatId} on server ${serverId}`
    );
    entry.disconnected = true;
  });
};

const processRequest = ({ req, res, next, disconnected }) => {
  return new Promise((resolve) => {
    let closeCalled = false;
    let finished = false;
    let checkFinishInterval;

    const done = () => {
      clearInterval(checkFinishInterval);
      resolve();
    };

    const finishHandler = () => {
      finished = true;
      if (closeCalled) {
        done();
      }
    };

    const closeHandler = () => {
      closeCalled = true;
      if (!finished) {
        checkFinishInterval = setInterval(() => {
          if (res.writableFinished) {
            finishHandler();
          }
        }, 50);
      } else {
        done();
      }
    };

    res.on("finish", finishHandler);
    res.on("close", closeHandler);

    if (!disconnected) {
      next();
    } else {
      done();
    }
  });
};

app.get("/", (req, res) => {
  res.json({
    message: "Welcome to ChatGPT API service",
  });
});

app.post("/start", async (req, res) => {
  const serverId = req.body.serverId || "default";
  const chatId = generateUniqueChatId();
  const storage = getServerStorage(serverId);

  storage.conversations[chatId] = {
    messages: [],
    conversationNo: 0,
    lastActivity: Date.now(),
    serverId,
    timeout: setTimeout(() => {
      closeChatSession(serverId, chatId);
    }, INACTIVITY_TIMEOUT),
  };

  storage.queues[chatId] = Promise.resolve();
  res.json({ chatId, serverId });
});

app.post("/conversation", sequentialMiddleware, async (req, res) => {
  const { chatId, prompt, serverId = "default" } = req.body;
  if (!chatId || !prompt) {
    return res.status(400).json({ message: "Chat ID and prompt are required" });
  }

  const storage = getServerStorage(serverId);
  const chatSession = storage.conversations[chatId];

  if (!chatSession) {
    return res.status(404).json({ message: "Chat session not found" });
  }

  chatSession.lastActivity = Date.now();
  clearTimeout(chatSession.timeout);
  chatSession.timeout = setTimeout(() => {
    closeChatSession(serverId, chatId);
  }, INACTIVITY_TIMEOUT);

  try {
    const promptResult = await processCompletion(
      serverId,
      chatId,
      prompt.toString()
    );
    if (promptResult.message) {
      closeChatSession(serverId, chatId);
      return res.status(429).json({
        message: promptResult.message,
      });
    }
    return res.json({ response: promptResult });
  } catch (error) {
    console.error("Error processing conversation:", error);
    return res.status(500).json({ message: "Error processing conversation" });
  }
});

async function processCompletion(serverId, chatId, prompt) {
  try {
    if (prompt.length > 4096) {
      prompt = prompt.substring(0, 4096);
    }
    console.log(
      `Processing prompt for chat ${chatId} on server ${serverId}: \n`,
      prompt
    );

    const storage = getServerStorage(serverId);
    const chatSession = storage.conversations[chatId];
    chatSession.conversationNo++;

    if (chatSession.conversationNo >= 20) {
      await closeChatSession(serverId, chatId);
      return "You've reached our limit of messages per hour. Please try again later.";
    }

    // Add user message to history
    chatSession.messages.push({ role: "user", content: prompt });

    if (chatSession.messages.length > 10) {
      chatSession.messages = chatSession.messages.slice(-10);
    }

    // Call LLM API with provider-specific configuration
    const response = await llmClient.chat.completions.create({
      model: process.env.MODEL_NAME || "gpt-3.5-turbo",
      messages: chatSession.messages,
      max_tokens: parseInt(process.env.MAX_TOKENS || "1000"),
      temperature: parseFloat(process.env.TEMPERATURE || "0.7"),
    });

    const responseText = response.choices[0].message.content;
    chatSession.messages.push({ role: "assistant", content: responseText });

    console.log(
      `Prompt response for chat ${chatId} on server ${serverId}: \n`,
      responseText
    );
    return responseText;
  } catch (error) {
    numErr++;
    await handleGlobalError(serverId);

    console.error(`API Error for server ${serverId}:`, error);

    // Handle provider-specific error cases
    if (
      error.response?.status === 429 ||
      error.message?.includes("rate limit")
    ) {
      await closeChatSession(serverId, chatId);
      return { message: "Rate limit exceeded. Please try again later." };
    }

    if (error.message?.includes("connect ECONNREFUSED")) {
      return {
        message:
          "LLM service not available. Please check the server connection.",
      };
    }

    await closeChatSession(serverId, chatId);
    return {
      message:
        "Error occurred during processing, please create a new chat session",
    };
  }
}

function generateUniqueChatId() {
  return "chat_" + Math.random().toString(36).substr(2, 9);
}

app.use((req, res, next) => {
  res.status(404).json({ message: "Route not found" });
});

app.use((err, req, res, next) => {
  console.error(err.stack);
  res.status(500).json({ message: "Internal server error" });
});

let port = 8080;

// Parse port from command line arguments
process.argv.forEach((arg, index) => {
  if (arg === "-p" && process.argv[index + 1]) {
    port = parseInt(process.argv[index + 1], 10);
  }
});

app.listen(port, () => {
  console.log(`Server is listening on port ${port}`);
});

// Cleanup function to call when the process is shutting down
async function cleanupBeforeExit() {
  console.log("Cleaning up before exit...");
  stopFetching = true;

  // Close all chat sessions for all servers
  Object.keys(serverConversations).forEach((serverId) => {
    const storage = getServerStorage(serverId);
    Object.keys(storage.conversations).forEach((chatId) => {
      closeChatSession(serverId, chatId);
    });
  });

  console.log("Cleanup complete");
}
