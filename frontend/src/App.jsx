import { useEffect, useState } from "react";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

function formatSeconds(value) {
  if (!value) return "0s";
  if (value < 60) return `${value}s`;
  const minutes = Math.floor(value / 60);
  const seconds = Math.floor(value % 60);
  return `${minutes}m ${seconds}s`;
}

export default function App() {
  const [summary, setSummary] = useState(null);
  const [recent, setRecent] = useState([]);
  const [error, setError] = useState("");
  const [simCallId, setSimCallId] = useState("");
  const [simLog, setSimLog] = useState([]);
  const [simInput, setSimInput] = useState("");
  const [simAudioFile, setSimAudioFile] = useState(null);
  const [simBusy, setSimBusy] = useState(false);

  useEffect(() => {
    const load = async () => {
      try {
        const summaryRes = await fetch(`${API_BASE_URL}/api/analytics/summary`);
        const summaryJson = await summaryRes.json();
        const recentRes = await fetch(`${API_BASE_URL}/api/analytics/recent`);
        const recentJson = await recentRes.json();
        setSummary(summaryJson);
        setRecent(recentJson.calls || []);
      } catch (err) {
        setError("Failed to load analytics.");
      }
    };
    load();
  }, []);

  const startSim = async () => {
    setSimBusy(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/simulator/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone_number: "" }),
      });
      const data = await res.json();
      setSimCallId(data.call_id);
      setSimLog([{ role: "agent", text: data.greeting }]);
    } finally {
      setSimBusy(false);
    }
  };

  const sendTurn = async () => {
    if (!simInput.trim() || !simCallId) return;
    const userText = simInput.trim();
    setSimInput("");
    setSimLog((prev) => [...prev, { role: "patient", text: userText }]);
    setSimBusy(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/simulator/turn`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ call_id: simCallId, text: userText }),
      });
      const data = await res.json();
      if (data.response_text) {
        setSimLog((prev) => [
          ...prev,
          { role: "agent", text: data.response_text, audio_url: data.audio_url || "" },
        ]);
      }
      if (data.call_complete) {
        await fetch(`${API_BASE_URL}/api/simulator/end`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ call_id: simCallId }),
        });
        setSimCallId("");
      }
    } finally {
      setSimBusy(false);
    }
  };

  const sendAudio = async () => {
    if (!simAudioFile || !simCallId) return;
    setSimBusy(true);
    try {
      const form = new FormData();
      form.append("call_id", simCallId);
      form.append("audio", simAudioFile);
      const res = await fetch(`${API_BASE_URL}/api/simulator/turn-audio`, {
        method: "POST",
        body: form,
      });
      const data = await res.json();
      if (data.user_text) {
        setSimLog((prev) => [...prev, { role: "patient", text: data.user_text }]);
      }
      if (data.response_text) {
        setSimLog((prev) => [
          ...prev,
          { role: "agent", text: data.response_text, audio_url: data.audio_url || "" },
        ]);
      }
      if (data.call_complete) {
        await fetch(`${API_BASE_URL}/api/simulator/end`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ call_id: simCallId }),
        });
        setSimCallId("");
      }
    } finally {
      setSimBusy(false);
      setSimAudioFile(null);
    }
  };

  if (error) {
    return (
      <div className="page">
        <div className="panel">
          <h1>Call Intelligence</h1>
          <p>{error}</p>
        </div>
      </div>
    );
  }

  if (!summary) {
    return (
      <div className="page">
        <div className="panel">
          <h1>Call Intelligence</h1>
          <p>Loading dashboard...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      <header className="hero">
        <div>
          <h1>Call Intelligence</h1>
          <p>Healthcare agent performance, intent mix, and outcomes in one view.</p>
        </div>
        <div className="chip">Live Analytics</div>
      </header>

      <section className="grid">
        <div className="card">
          <span>Total Calls</span>
          <strong>{summary.total_calls}</strong>
        </div>
        <div className="card">
          <span>Successful</span>
          <strong>{summary.successful_calls}</strong>
        </div>
        <div className="card">
          <span>Failed</span>
          <strong>{summary.failed_calls}</strong>
        </div>
        <div className="card">
          <span>Avg Duration</span>
          <strong>{formatSeconds(summary.avg_duration_seconds)}</strong>
        </div>
      </section>

      <section className="panel">
        <h2>Intent Distribution</h2>
        <div className="bars">
          {summary.intent_distribution.map((item) => (
            <div key={item.intent} className="bar-row">
              <div className="bar-label">{item.intent}</div>
              <div className="bar-track">
                <div
                  className="bar-fill"
                  style={{ width: `${Math.min(item.count * 10, 100)}%` }}
                ></div>
              </div>
              <div className="bar-count">{item.count}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="panel">
        <h2>Failure Reasons</h2>
        {summary.failure_reasons.length === 0 ? (
          <p>No failures recorded.</p>
        ) : (
          <ul className="list">
            {summary.failure_reasons.map((item) => (
              <li key={item.reason}>
                <span>{item.reason}</span>
                <strong>{item.count}</strong>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="panel">
        <h2>Recent Calls</h2>
        <div className="table">
          <div className="table-row table-head">
            <span>Call ID</span>
            <span>Purpose</span>
            <span>Status</span>
            <span>Started</span>
          </div>
          {recent.map((call) => (
            <div className="table-row" key={call.call_id}>
              <span className="mono">{call.call_id.slice(0, 8)}...</span>
              <span>{call.purpose}</span>
              <span className={call.success ? "success" : "failure"}>
                {call.success ? "Success" : "Failed"}
              </span>
              <span>{call.start_time ? new Date(call.start_time).toLocaleString() : "-"}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="panel">
        <h2>Call Simulator</h2>
        <p className="muted">
          Test the conversation flow locally without Twilio. Start a call, send messages,
          and watch the agent respond.
        </p>
        <div className="sim-controls">
          <button className="primary" onClick={startSim} disabled={simBusy || !!simCallId}>
            {simCallId ? "Call Active" : "Start Call"}
          </button>
          {simCallId && <span className="mono">Call ID: {simCallId.slice(0, 8)}...</span>}
        </div>
        <div className="sim-log">
          {simLog.length === 0 && <div className="sim-empty">No messages yet.</div>}
          {simLog.map((item, idx) => (
            <div key={`${item.role}-${idx}`} className={`bubble ${item.role}`}>
              <span className="role">{item.role}</span>
              <p>{item.text}</p>
              {item.audio_url && (
                <audio controls src={item.audio_url}>
                  Your browser does not support audio playback.
                </audio>
              )}
            </div>
          ))}
        </div>
        <div className="sim-input">
          <input
            type="text"
            placeholder="Type the patient's request..."
            value={simInput}
            onChange={(event) => setSimInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                sendTurn();
              }
            }}
            disabled={!simCallId || simBusy}
          />
          <button onClick={sendTurn} disabled={!simCallId || simBusy}>
            Send
          </button>
        </div>
        <div className="sim-audio">
          <input
            type="file"
            accept="audio/wav"
            onChange={(event) => setSimAudioFile(event.target.files?.[0] || null)}
            disabled={!simCallId || simBusy}
          />
          <button onClick={sendAudio} disabled={!simCallId || simBusy || !simAudioFile}>
            Send Audio
          </button>
          <span className="muted">WAV only (16-bit PCM recommended)</span>
        </div>
      </section>
    </div>
  );
}
