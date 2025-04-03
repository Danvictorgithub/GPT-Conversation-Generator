import express from "express";
import dotenv from "dotenv";
import path from "path";
import { fileURLToPath } from "url";

// Get directory name in ES module
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Load .env from root directory
dotenv.config({ path: path.join(__dirname, "..", ".env") });

import process from "process";
import { OpenAI } from "openai";

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
  const provider = process.env.LLM_PROVIDER?.toLowerCase() || "lmstudio";
  console.log(`Initializing LLM client for provider: ${provider}`);
  console.log(`Using base URL: ${process.env.LLM_BASE_URL}`);

  const config = {
    apiKey: process.env.LLM_API_KEY || "sk-no-key-required",
    baseURL: process.env.LLM_BASE_URL || "http://localhost:1234/v1",
    defaultHeaders: {
      "Content-Type": "application/json",
    },
    dangerouslyAllowBrowser: true,
    maxRetries: 3,
    timeout: 120000, // Increase timeout to 120 seconds
    defaultQuery: { timeout: 120 }, // Add query parameter for timeout
    defaultParams: { timeout: 120 }, // Add params for timeout
  };

  console.log("LLM Configuration:", {
    ...config,
    apiKey: "[HIDDEN]",
  });

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

// Add this helper function for cleaning responses
function cleanResponse(text) {
  if (!text) return text;

  // Remove think tags and their content
  let cleaned = text.replace(/<think>[\s\S]*?<\/think>/g, "");

  // Split by newlines and remove empty lines
  let lines = cleaned.split("\n").filter((line) => line.trim());

  // Get the last non-empty line as it's usually the final response
  let finalResponse = lines[lines.length - 1] || "";

  return finalResponse.trim();
}

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

    // Add system message to enforce response format
    const messages = [
      {
        role: "system",
        content:
          "Provide direct responses without thinking out loud. Avoid using phrases like 'let me think' or explanatory prefixes. Give natural, conversational responses.",
      },
      ...chatSession.messages,
    ];

    console.log("Sending request to LLM service with configuration:", {
      model: process.env.MODEL_NAME,
      max_tokens: parseInt(process.env.MAX_TOKENS || "1000"),
      temperature: parseFloat(process.env.TEMPERATURE || "0.7"),
      timeout: 120,
    });

    const response = await Promise.race([
      llmClient.chat.completions.create({
        model: process.env.MODEL_NAME,
        messages: messages,
        max_tokens: parseInt(process.env.MAX_TOKENS || "1000"),
        temperature: parseFloat(process.env.TEMPERATURE || "0.7"),
        stream: false,
        timeout: 120,
      }),
      new Promise((_, reject) =>
        setTimeout(
          () => reject(new Error("Request timeout after 120s")),
          120000
        )
      ),
    ]);

    // Clean the response using our helper function
    const responseText = cleanResponse(response.choices[0].message.content);
    chatSession.messages.push({ role: "assistant", content: responseText });

    console.log(
      `Cleaned response for chat ${chatId} on server ${serverId}: \n`,
      responseText
    );
    return responseText;
  } catch (error) {
    console.error("Detailed error:", {
      message: error.message,
      name: error.name,
      code: error.code,
      response: error.response,
      stack: error.stack,
    });

    numErr++;
    await handleGlobalError(serverId);

    if (
      error.message?.includes("timeout") ||
      error.message?.includes("ECONNREFUSED")
    ) {
      console.error(
        `Connection issue with LM Studio (${error.message}). Please ensure it's running and not overloaded.`
      );
      return {
        message:
          "LLM service is currently busy or unavailable. Please try again later.",
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

app.listen(port, async () => {
  console.log(`Server is listening on port ${port}`);

  // Test LLM connection with timeout
  try {
    const response = await Promise.race([
      llmClient.chat.completions.create({
        model: process.env.MODEL_NAME,
        messages: [{ role: "user", content: "test" }],
        max_tokens: 5,
        timeout: 30,
      }),
      new Promise((_, reject) =>
        setTimeout(() => reject(new Error("Initial connection timeout")), 30000)
      ),
    ]);
    console.log("Successfully connected to LLM service");
  } catch (error) {
    console.error("Failed to connect to LLM service:", error.message);
    console.log("Please ensure LM Studio is:");
    console.log("1. Running and accessible at:", process.env.LLM_BASE_URL);
    console.log("2. Has the correct model loaded:", process.env.MODEL_NAME);
    console.log("3. API is enabled in LM Studio");
    console.log("4. Not overloaded with requests");
  }
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
