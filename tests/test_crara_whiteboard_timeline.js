const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("frontend/resources/crara-classroom/crara-whiteboard.js", "utf8");
const packets = [];
const domEvents = [];
const speakCalls = [];
const instructionCalls = [];
const storage = new Map();
let instructionResponseOverride = null;

const session = {
  status: "connected",
  roomName: "crara_general_test",
  selfName: "crara-e2e-host",
  publishWhiteboardData(topic, packet) {
    packets.push({ topic, packet });
    return Promise.resolve();
  },
};

class AudioMock {
  constructor(src) {
    this.src = src;
    this.currentTime = 0;
    this.listeners = new Map();
  }
  addEventListener(name, callback) {
    const list = this.listeners.get(name) || [];
    list.push(callback);
    this.listeners.set(name, list);
  }
  play() {
    (this.listeners.get("play") || []).forEach((callback) => callback());
    return Promise.resolve();
  }
  pause() {
    (this.listeners.get("pause") || []).forEach((callback) => callback());
  }
}

class TextDecoderMock {
  decode(value) {
    return Buffer.from(value).toString("utf8");
  }
}

class CustomEventMock {
  constructor(type, options) {
    this.type = type;
    this.detail = options && options.detail;
  }
}

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function fetchMock(url, options = {}) {
  if (url === "/api/class-rep/speak") {
    speakCalls.push(JSON.parse(options.body || "{}"));
    await wait(250);
    return {
      ok: true,
      status: 200,
      headers: { get: () => "audio/mpeg" },
      blob: async () => ({ size: 1 }),
    };
  }
  if (url === "/api/class-rep/whiteboard/instructions") {
    instructionCalls.push(JSON.parse(options.body || "{}"));
    return {
      ok: true,
      status: 200,
      json: async () => instructionResponseOverride || {
        narration: "State H0.",
        caption: "Decision flow",
        instructions: [],
        speak: true,
        control: { type: "teaching", value: { value: "teaching" }, token: "test-token" },
      },
    };
  }
  return { ok: false, status: 404 };
}

const window = {
  localStorage: {
    getItem: (key) => (storage.has(key) ? storage.get(key) : null),
    setItem: (key, value) => storage.set(key, String(value)),
  },
  addEventListener() {},
  dispatchEvent(event) { domEvents.push(event); return true; },
  setTimeout: (callback, ms) => setTimeout(callback, ms),
  clearTimeout: (id) => clearTimeout(id),
  prompt: () => null,
  __craraClassroomRole: "host",
  __craraClassroomPermissions: {
    canWrite: true,
    canControl: true,
    boardLocked: false,
    boardOwner: "",
    granted: [],
  },
  __craraWhiteboardSession: session,
};

const document = {
  readyState: "complete",
  body: { classList: { add() {}, remove() {} } },
  addEventListener() {},
  createElement: () => ({
    style: {},
    className: "",
    dataset: {},
    setAttribute() {},
    appendChild() {},
    replaceChildren() {},
    addEventListener() {},
  }),
};

const context = {
  window,
  document,
  fetch: fetchMock,
  Audio: AudioMock,
  TextDecoder: TextDecoderMock,
  CustomEvent: CustomEventMock,
  URL: { createObjectURL: () => "blob:crara-voice" },
  AbortController,
  console,
};

(async () => {
  vm.runInNewContext(source, context, { filename: "crara-whiteboard.js" });
  const api = window.__craraWhiteboard;
  assert.ok(api, "whiteboard API should be exposed");

  const firstTimeline = {
    id: "tl-test-1",
    lesson: "Hypothesis Testing",
    durationMs: 700,
    segments: [
      { id: "s1", type: "TEACHING", atMs: 0, payload: { value: "teaching" } },
      { id: "s2", type: "CAPTION", atMs: 0, payload: { text: "Hypothesis testing" } },
      { id: "s3", type: "SPEAK", atMs: 10, payload: { text: "State H0." } },
      {
        id: "s4", type: "BOARD", atMs: 20,
        payload: { instruction: { type: "WRITE_TEXT", args: { text: "H0", x: 80, y: 120 } } },
      },
      {
        id: "s5", type: "BOARD", atMs: 30,
        payload: { instruction: { type: "RENDER_EQUATION", args: { latex: "z=1", x: 80, y: 220 } } },
      },
    ],
  };

  assert.equal(api.loadTimeline(firstTimeline, true), true);
  const started = Date.now();
  const results = await api.runTimeline();
  const elapsed = Date.now() - started;
  assert.equal(results.length, 5);
  assert.ok(elapsed < 200, `board timeline must not wait for delayed voice, took ${elapsed}ms`);
  assert.equal(api.getState().pages[0].objects.length, 2);
  assert.ok(packets.some((entry) => entry.packet.type === "segment" && entry.packet.segmentId === "s4"));
  assert.equal(speakCalls.length, 1, "speech segment should call the existing /speak endpoint");
  await wait(320);
  assert.ok(packets.some((entry) => entry.packet.type === "speech"), "speech events should be published");

  const speechPacketsBeforeRemote = packets.filter((entry) => entry.packet.type === "speech").length;
  const speakCallsBeforeRemote = speakCalls.length;
  assert.equal(api.loadTimeline({
    id: "tl-remote",
    lesson: "Hypothesis Testing",
    durationMs: 500,
    segments: [{ id: "r1", type: "SPEAK", atMs: 50, payload: { text: "Remote narration." } }],
  }, false), true);
  api.setTeachingState("teaching");
  api.onRemote("crara-whiteboard", Buffer.from(JSON.stringify({
    v: 1,
    type: "segment",
    actor: "remote-host",
    seq: Date.now() + 10000,
    lesson: "Hypothesis Testing",
    segmentId: "r1",
    segmentType: "SPEAK",
    atMs: 50,
    timelineId: "tl-remote",
  })));
  await wait(320);
  assert.equal(speakCalls.length, speakCallsBeforeRemote + 1, "followers should play narration from the existing /speak endpoint");
  assert.equal(
    packets.filter((entry) => entry.packet.type === "speech").length,
    speechPacketsBeforeRemote,
    "follower playback must not echo authoritative speech events"
  );

  const beforePause = api.getState().pages[0].objects.length;
  const secondTimeline = {
    id: "tl-test-2",
    lesson: "Hypothesis Testing",
    durationMs: 700,
    segments: [
      {
        id: "p1", type: "BOARD", atMs: 0,
        payload: { instruction: { type: "DRAW_LINE", args: { x1: 10, y1: 10, x2: 90, y2: 90 } } },
      },
      {
        id: "p2", type: "BOARD", atMs: 60,
        payload: { instruction: { type: "DRAW_ARROW", args: { x1: 20, y1: 20, x2: 80, y2: 80 } } },
      },
    ],
  };
  api.loadTimeline(secondTimeline, true);
  const running = api.runTimeline();
  await wait(20);
  assert.equal(api.getState().pages[0].objects.length, beforePause + 1);
  api.pauseLesson(false);
  const partial = await running;
  assert.equal(partial.length, 1, "pausing must cancel the remaining timeline segments");
  assert.equal(api.getState().timeline.status, "paused");
  api.resumeLesson();
  await wait(140);
  assert.equal(api.getState().pages[0].objects.length, beforePause + 2);
  assert.equal(api.getState().timeline.status, "complete");

  const beforeInterrupt = api.getState().pages[0].objects.length;
  const thirdTimeline = {
    id: "tl-test-3",
    lesson: "Hypothesis Testing",
    durationMs: 700,
    segments: [
      {
        id: "i1", type: "BOARD", atMs: 0,
        payload: { instruction: { type: "DRAW_CIRCLE", args: { x1: 10, y1: 10, x2: 60, y2: 60 } } },
      },
      {
        id: "i2", type: "BOARD", atMs: 80,
        payload: { instruction: { type: "DRAW_RECTANGLE", args: { x1: 20, y1: 20, x2: 70, y2: 70 } } },
      },
    ],
  };
  api.loadTimeline(thirdTimeline, true);
  const interruptedRun = api.runTimeline();
  await wait(15);
  api.interruptLesson("Microphone opened — CRARA is listening.");
  const interruptedResults = await interruptedRun;
  assert.equal(interruptedResults.length, 1, "interruption must stop later board segments");
  assert.equal(api.getState().timeline.status, "interrupted");
  assert.equal(api.getState().pages[0].objects.length, beforeInterrupt + 1);
  assert.ok(packets.some((entry) => entry.packet.type === "interrupt"));

  const statePacket = (seq) => ({
    v: 1,
    type: "state",
    actor: "remote-host",
    seq,
    lesson: "Hypothesis Testing",
    pageIndex: 0,
    pages: [{
      id: "remote-page",
      objects: [{ id: "remote-obj-" + seq, type: "text", x: 10, y: 10, text: "Remote " + seq }],
    }],
  });
  api.onRemote("crara-whiteboard", Buffer.from(JSON.stringify(statePacket(9000000000000))));
  assert.equal(api.getState().pages[0].objects[0].id, "remote-obj-9000000000000");
  api.onRemote("crara-whiteboard", Buffer.from(JSON.stringify(statePacket(8999999999999))));
  assert.equal(api.getState().pages[0].objects[0].id, "remote-obj-9000000000000", "stale per-actor packets must be ignored");
  api.onRemote("crara-whiteboard", Buffer.from(JSON.stringify(statePacket(9000000000001))));
  assert.equal(api.getState().pages[0].objects[0].id, "remote-obj-9000000000001");

  const questionCallsBefore = instructionCalls.length;
  const questionPacket = (seq) => ({
    v: 1,
    type: "question",
    actor: "remote-student",
    seq,
    lesson: "Hypothesis Testing",
    id: "q-dedupe",
    body: "What is alpha?",
    from: "Student",
  });
  api.onRemote("crara-whiteboard", Buffer.from(JSON.stringify(questionPacket(9000000000000))));
  await wait(220);
  assert.equal(instructionCalls.length, questionCallsBefore + 1, "host should answer a remote question once");
  api.onRemote("crara-whiteboard", Buffer.from(JSON.stringify(questionPacket(9000000000001))));
  await wait(220);
  assert.equal(instructionCalls.length, questionCallsBefore + 1, "duplicate question packets must not trigger duplicate answers");

  const pagesBeforeInvalid = api.getState().pages[0].objects.length;
  const errorsBeforeInvalid = packets.filter((entry) => entry.packet.type === "instruction-error").length;
  instructionResponseOverride = {
    narration: "Broken timeline narration.",
    caption: "Broken timeline",
    speak: true,
    instructions: [{ type: "WRITE_TEXT", args: { text: "should not draw", x: 1, y: 1 } }],
    timeline: { id: "tl-invalid", segments: [] },
    control: { type: "teaching", value: { value: "teaching" }, token: "test-token" },
  };
  await api.respondToQuestion({ id: "invalid-timeline", body: "Broken", from: "Student", mine: true });
  instructionResponseOverride = null;
  assert.equal(api.getState().pages[0].objects.length, pagesBeforeInvalid, "a rejected timeline must not draw stale instructions");
  assert.equal(
    packets.filter((entry) => entry.packet.type === "instruction-error").length,
    errorsBeforeInvalid + 1,
    "invalid timelines must publish a recoverable error"
  );

  // A locally typed classroom chat message must drive the same synchronized
  // timeline even when the participant is not the host and no host is present.
  api.setRole("student");
  const chatCallsBefore = instructionCalls.length;
  const domEventsBeforeChat = domEvents.length;
  await api.onChat({ id: "chat-local-student", body: "What is alpha?", from: "Student", mine: true });
  assert.equal(instructionCalls.length, chatCallsBefore + 1, "local classroom chat must trigger a synchronized answer");
  const answerEvents = domEvents.slice(domEventsBeforeChat).filter((event) => event.type === "crara-whiteboard-answer");
  assert.equal(answerEvents.length, 1, "CRARA answers must be emitted into the classroom chat");
  assert.ok(answerEvents[0].detail.body, "the chat answer event must carry visible text");
  const localQuestionPackets = packets.filter((entry) => entry.packet.id === "chat-local-student");
  assert.equal(localQuestionPackets.length, 1, "local chat should publish one authoritative question packet");
  assert.equal(localQuestionPackets[0].packet.answered, true, "the answering sender must mark the question as answered");
  await wait(320);

  // A host must not answer a question that the sending participant already
  // answered locally, otherwise two timelines would fight over the board.
  api.setRole("host");
  const hostCallsBefore = instructionCalls.length;
  api.onRemote("crara-whiteboard", Buffer.from(JSON.stringify({
    v: 1,
    type: "question",
    actor: "remote-student-answered",
    seq: 9000000000002,
    lesson: "Hypothesis Testing",
    id: "q-answered-elsewhere",
    body: "Already answered locally",
    from: "Student",
    answered: true,
  })));
  await wait(220);
  assert.equal(instructionCalls.length, hostCallsBefore, "hosts must ignore questions already answered by the sender");

  // Remote chat callbacks only update the visible transcript; the whiteboard
  // question packet is the single source of answer work.
  const questionPacketsBeforeRemoteChat = packets.filter((entry) => entry.packet.type === "question").length;
  api.onChat({ id: "remote-chat-callback", body: "Remote only", from: "Student", mine: false });
  assert.equal(
    packets.filter((entry) => entry.packet.type === "question").length,
    questionPacketsBeforeRemoteChat,
    "remote chat callbacks must not re-publish question packets"
  );

  // Chat sent while CRARA is busy is retained and answered after the current
  // response, rather than silently dropped.
  api.setRole("student");
  const busyAnswer = api.respondToQuestion({ id: "busy-answer", body: "Busy", from: "Student", mine: true });
  api.onChat({ id: "chat-queued", body: "Queue me", from: "Student", mine: true });
  const queuedPackets = packets.filter((entry) => entry.packet.id === "chat-queued");
  assert.equal(queuedPackets.length, 1, "busy chat should still publish its question packet");
  assert.equal(queuedPackets[0].packet.answered, true);
  const beforeQueuedAnswer = instructionCalls.length;
  await busyAnswer;
  await wait(120);
  assert.equal(instructionCalls.length, beforeQueuedAnswer + 1, "queued chat must be answered after the current response");

  console.log("CRARA whiteboard timeline checks passed.");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
