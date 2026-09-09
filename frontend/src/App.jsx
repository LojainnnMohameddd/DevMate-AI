import { useState } from "react";
import "./App.css";

const API_BASE_URL = "http://127.0.0.1:8080";

const iconPaths = {
  spark: "M12 2.8l1.25 5.05L18.3 9.1l-5.05 1.25L12 15.4l-1.25-5.05L5.7 9.1l5.05-1.25L12 2.8Z",
  plan: "M6 3.5h8l4 4v13H6a2 2 0 0 1-2-2v-13a2 2 0 0 1 2-2Z M14 3.5v5h4 M8 12h6M8 16h6",
  code: "M8.2 7 3.8 12l4.4 5M15.8 7l4.4 5-4.4 5M13.7 4.8 10.3 19.2",
  shield: "M12 3 20 6v5.3c0 4.7-3.1 8.3-8 9.7-4.9-1.4-8-5-8-9.7V6l8-3Z M8.3 12.1l2.2 2.2 5.1-5.1",
  eye: "M2.5 12s3.3-5.2 9.5-5.2 9.5 5.2 9.5 5.2-3.3 5.2-9.5 5.2S2.5 12 2.5 12Z M12 14.8a2.8 2.8 0 1 0 0-5.6 2.8 2.8 0 0 0 0 5.6Z",
  layers: "M12 3.5 21 8l-9 4.5L3 8l9-4.5Z M3 12l9 4.5 9-4.5 M3 16l9 4.5 9-4.5",
  play: "M8 5.5v13l10-6.5-10-6.5Z",
  wrench: "M20.2 6.1a5.2 5.2 0 0 1-6.8 6.8L7 19.3a2 2 0 1 1-2.8-2.8l6.4-6.4a5.2 5.2 0 0 1 6.8-6.8l-3 3 2.1 2.1 3.7-2.3Z",
  arrow: "M5 12h13M13 6l6 6-6 6",
  download: "M12 3v11M7.5 10.5 12 15l4.5-4.5M5 20h14",
  check: "M5 12.5 9.2 17 19 7",
  alert: "M12 4 21 20H3L12 4Zm0 5.5v4.2M12 17.2h.01",
  folder: "M3.5 6.5h5l1.7 2h10.3v9.8a1.7 1.7 0 0 1-1.7 1.7H5.2a1.7 1.7 0 0 1-1.7-1.7V6.5Z",
  file: "M6 3.5h7l5 5v12H6a2 2 0 0 1-2-2v-13a2 2 0 0 1 2-2Z M13 3.5v5h5",
  spinner: "M12 3a9 9 0 1 0 9 9",
};

function Icon({ name, size = 18, strokeWidth = 1.8, className = "" }) {
  const d = iconPaths[name] || iconPaths.spark;
  const isFill = name === "spark";
  return (
    <svg
      className={`icon ${className}`}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill={isFill ? "currentColor" : "none"}
      stroke={isFill ? "none" : "currentColor"}
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={d} />
    </svg>
  );
}

function App() {
  const [request, setRequest] = useState("");
  const [status, setStatus] = useState("idle");
  const [result, setResult] = useState(null);
  const [currentStep, setCurrentStep] = useState("planner");
  const [pipelineState, setPipelineState] = useState({
    planner: "active",
    coder: "waiting",
    validator: "waiting",
    reviewer: "waiting",
    mcp: "waiting",
    executor: "waiting",
    fixer: "waiting",
  });

  const [projectFiles, setProjectFiles] = useState([]);
  const [selectedFile, setSelectedFile] = useState(null);
  const [fileContent, setFileContent] = useState("");
  const [fileLoading, setFileLoading] = useState(false);

  const handleGenerate = async () => {
    if (!request.trim() || status === "generating") {
      return;
    }

    setStatus("generating");
    setResult(null);
    setProjectFiles([]);
    setSelectedFile(null);
    setFileContent("");
    setCurrentStep("planner");
    setPipelineState({
      planner: "running",
      coder: "waiting",
      validator: "waiting",
      reviewer: "waiting",
      mcp: "waiting",
      executor: "waiting",
      fixer: "waiting",
    });

    try {
      const response = await fetch(`${API_BASE_URL}/generate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          request: request.trim(),
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail ||
          data.message ||
          "Project generation failed."
        );
      }

      const jobId = data.generation_id;

      if (!jobId) {
        throw new Error("Generation job was not created.");
      }


      let finished = false;

      while (!finished) {
        await new Promise((resolve) =>
          setTimeout(resolve, 700)
        );

        const statusResponse = await fetch(
          `${API_BASE_URL}/generate/${encodeURIComponent(jobId)}`
        );

        const statusData = await statusResponse.json();

        if (!statusResponse.ok) {
          throw new Error(
            statusData.detail ||
            "Failed to read generation status."
          );
        }

        const nextPipelineState = {
          planner: "waiting",
          coder: "waiting",
          validator: "waiting",
          reviewer: "waiting",
          mcp: "waiting",
          executor: "waiting",
          fixer: "waiting",
        };

        (statusData.history || []).forEach((event) => {
          if (event.step in nextPipelineState) {
            nextPipelineState[event.step] = event.state;
          }
        });

        if (statusData.step in nextPipelineState) {
          nextPipelineState[statusData.step] =
            statusData.step_state || "running";
          setCurrentStep(statusData.step);
        }

        setPipelineState(nextPipelineState);

        if (statusData.status === "completed") {
          finished = true;
          setStatus("completed");
          setResult({
            status: "completed",
            message:
              statusData.message ||
              "Project generated successfully",
            project_path: statusData.project_path,
            execution: statusData.execution,
          });

          if (statusData.project_path) {
            await loadProjectFiles(
              statusData.project_path
            );
          }
        } else if (statusData.status === "failed") {
          finished = true;
          setStatus("failed");
          setResult({
            status: "failed",
            message:
              statusData.message ||
              "Project generation failed.",
            project_path: statusData.project_path,
            execution: statusData.execution,
          });
        }
      }
    } catch (error) {
      console.error("Generation error:", error);

      setStatus("failed");

      setPipelineState((previous) => ({
        ...previous,
        [currentStep]: "failed",
      }));

      setResult({
        status: "failed",
        message:
          error.message ||
          "Unable to connect to the DevMate backend.",
      });
    }
  };


  const getProjectName = (projectPath) => {
    if (!projectPath) {
      return "";
    }

    return projectPath
      .replaceAll("\\", "/")
      .split("/")
      .filter(Boolean)
      .pop();
  };

  const loadProjectFiles = async (projectPath) => {
    const projectName = getProjectName(projectPath);

    if (!projectName) {
      return;
    }

    try {
      const response = await fetch(
        `${API_BASE_URL}/projects/${encodeURIComponent(
          projectName
        )}/files`
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Failed to load project files."
        );
      }

      setProjectFiles(data.files || []);
    } catch (error) {
      console.error("File loading error:", error);

      setProjectFiles([]);
    }
  };

  const handleFileSelect = async (file) => {
    if (!result?.project_path) {
      return;
    }

    const projectName = getProjectName(
      result.project_path
    );

    setSelectedFile(file);
    setFileContent("");
    setFileLoading(true);

    try {
      const response = await fetch(
        `${API_BASE_URL}/projects/${encodeURIComponent(
          projectName
        )}/files/${file.path
          .split("/")
          .map(encodeURIComponent)
          .join("/")}`
      );

      if (!response.ok) {
        const errorData = await response.json().catch(
          () => null
        );

        throw new Error(
          errorData?.detail ||
          "Failed to load file."
        );
      }

      const content = await response.text();

      setFileContent(content);
    } catch (error) {
      console.error("File read error:", error);

      setFileContent(
        `Unable to load this file.\n\n${error.message}`
      );
    } finally {
      setFileLoading(false);
    }
  };

  const handleDownload = () => {
    if (!result?.project_path) {
      return;
    }

    const projectName = getProjectName(
      result.project_path
    );

    if (!projectName) {
      return;
    }

    window.location.href =
      `${API_BASE_URL}/projects/${encodeURIComponent(
        projectName
      )}/download`;
  };

  const getFileExtension = (fileName) => {
    if (!fileName) {
      return "CODE";
    }

    const parts = fileName.split(".");

    if (parts.length < 2) {
      return "TEXT";
    }

    return parts.pop().toUpperCase();
  };

  const getStepClass = (step) => {
    const state = pipelineState[step];

    if (state === "running") {
      return "pipeline-step active running";
    }

    if (state === "completed") {
      return "pipeline-step completed";
    }

    if (state === "failed") {
      return "pipeline-step active failed";
    }

    if (status === "idle" && step === "planner") {
      return "pipeline-step active";
    }

    return "pipeline-step";
  };

  const pipelineSteps = [
    {
      id: "planner",
      number: "01",
      icon: "plan",
      title: "Planner",
      description: "Turns your request into an actionable engineering plan.",
    },
    {
      id: "coder",
      number: "02",
      icon: "code",
      title: "Coder",
      description: "Generates the project structure and source code.",
    },
    {
      id: "validator",
      number: "03",
      icon: "shield",
      title: "Validator",
      description: "Checks files, imports, dependencies, and structure.",
    },
    {
      id: "reviewer",
      number: "04",
      icon: "eye",
      title: "Reviewer",
      description: "Reviews the implementation against your request.",
    },
    {
      id: "mcp",
      number: "05",
      icon: "layers",
      title: "MCP Writer",
      description: "Creates and writes the generated files to disk.",
    },
    {
      id: "executor",
      number: "06",
      icon: "play",
      title: "Executor",
      description: "Runs the generated project and checks runtime behavior.",
    },
    {
      id: "fixer",
      number: "07",
      icon: "wrench",
      title: "Fixer",
      description: "Diagnoses runtime issues and applies targeted fixes.",
    },
  ];

  const completedStages = pipelineSteps.filter(
    (step) => pipelineState[step.id] === "completed"
  ).length;

  const runningStage = pipelineSteps.find(
    (step) => pipelineState[step.id] === "running"
  );

  const progressPercent = Math.round(
    (completedStages / pipelineSteps.length) * 100
  );

  const activeLabel =
    status === "generating"
      ? runningStage?.title || currentStep.toUpperCase()
      : status === "completed"
        ? "Complete"
        : status === "failed"
          ? "Attention required"
          : "Ready";

  return (
    <div className="app">
      {/* =========================
          NAVBAR
         ========================= */}

      <header className="navbar">
        <div className="logo">
          <span className="logo-mark">&gt;_</span>

          <span>
            DevMate
            <span className="logo-accent">-AI</span>
          </span>
        </div>

        <div className="status">
          <span
            className={`status-dot ${status === "generating"
              ? "status-running"
              : status === "failed"
                ? "status-failed"
                : ""
              }`}
          />

          {status === "generating"
            ? "Generating..."
            : status === "completed"
              ? "Generation Complete"
              : status === "failed"
                ? "Generation Failed"
                : "System Ready"}
        </div>
      </header>

      <main className="main-content">
        {/* =========================
            HERO
           ========================= */}

        <section className="hero">
          <div className="badge">
            <Icon name="spark" size={14} />
            AI SOFTWARE ENGINEERING AGENT
          </div>

          <h1 className="hero-title">
            <span className="hero-line hero-line-main">Build software with</span>
            <span className="hero-line hero-line-accent">intelligent agents</span>
          </h1>

          <p className="subtitle">
            Describe what you want to build. DevMate plans,
            generates, validates, reviews, and executes your
            project automatically.
          </p>
        </section>

        {/* =========================
            GENERATOR
           ========================= */}

        <section className="generator-card">
          <div className="card-header">
            <div>
              <h2>What do you want to build?</h2>

              <p>
                Describe your project in natural language.
              </p>
            </div>

            <span className="request-label">
              PROJECT REQUEST
            </span>
          </div>

          <textarea
            value={request}
            onChange={(event) =>
              setRequest(event.target.value)
            }
            placeholder="Example: Create a FastAPI student management system with CRUD operations..."
            rows={7}
            disabled={status === "generating"}
          />

          <div className="card-footer">
            <span className="hint">
              {status === "generating"
                ? "DevMate is working on your project..."
                : "DevMate will handle the engineering workflow for you."}
            </span>

            <button
              className="generate-button"
              onClick={handleGenerate}
              disabled={
                !request.trim() ||
                status === "generating"
              }
            >
              <span>
                {status === "generating"
                  ? "Generating..."
                  : "Generate Project"}
              </span>

              <span className="arrow">
                {status === "generating" ? (
                  <Icon name="spinner" size={17} className="spin" />
                ) : (
                  <Icon name="arrow" size={17} />
                )}
              </span>
            </button>
          </div>
        </section>

        {/* =========================
            RESULT
           ========================= */}

        {result && (
          <section
            className={`result-card ${status === "completed"
              ? "result-success"
              : "result-error"
              }`}
          >
            <div className="result-icon">
              <Icon
                name={status === "completed" ? "check" : "alert"}
                size={18}
              />
            </div>

            <div className="result-content">
              <h3>
                {status === "completed"
                  ? "Project generated successfully"
                  : "Project generation failed"}
              </h3>

              <p>
                {result.message ||
                  "No additional information available."}
              </p>

              {result.project_path && (
                <span className="project-path">
                  {result.project_path}
                </span>
              )}
            </div>
          </section>
        )}

        {/* =========================
            PROJECT VIEWER
           ========================= */}

        {status === "completed" && (
          <section className="project-viewer">
            <div className="project-viewer-header">
              <div>
                <div className="viewer-eyebrow">
                  GENERATED PROJECT
                </div>

                <h2>
                  {getProjectName(
                    result?.project_path
                  ) || "Project"}
                </h2>
              </div>

              <div className="viewer-actions">
                <button
                  className="viewer-button"
                  type="button"
                  onClick={handleDownload}
                  title="Download project as ZIP"
                >
                  <Icon name="download" size={15} />
                  Download
                </button>
              </div>
            </div>

            <div className="viewer-body">
              {/* FILE EXPLORER */}

              <aside className="file-explorer">
                <div className="explorer-header">
                  <span>EXPLORER</span>

                  <span className="explorer-count">
                    {projectFiles.length} FILES
                  </span>
                </div>

                <div className="file-list">
                  {projectFiles.length === 0 ? (
                    <div className="explorer-empty">
                      <div className="empty-folder-icon">
                        <Icon name="folder" size={26} />
                      </div>

                      <h3>No files found</h3>

                      <p>
                        The generated project does not
                        contain readable files.
                      </p>
                    </div>
                  ) : (
                    projectFiles.map((file) => (
                      <button
                        key={file.path}
                        type="button"
                        className={`file-item ${selectedFile?.path === file.path
                          ? "selected"
                          : ""
                          }`}
                        onClick={() =>
                          handleFileSelect(file)
                        }
                      >
                        <span className="file-icon">
                          <Icon
                            name={file.name.startsWith(".") ? "file" : "file"}
                            size={13}
                          />
                        </span>

                        <span className="file-name">
                          {file.path}
                        </span>
                      </button>
                    ))
                  )}
                </div>
              </aside>

              {/* CODE VIEWER */}

              <section className="code-viewer">
                <div className="code-header">
                  <div className="code-tab">
                    {selectedFile
                      ? selectedFile.path
                      : "No file selected"}
                  </div>

                  <div className="code-language">
                    {selectedFile
                      ? getFileExtension(
                        selectedFile.name
                      )
                      : "CODE"}
                  </div>
                </div>

                <div className="code-content">
                  {!selectedFile ? (
                    <div className="code-empty">
                      <div className="code-empty-icon">
                        <Icon name="code" size={30} />
                      </div>

                      <h3>Select a file</h3>

                      <p>
                        Choose a project file from the
                        explorer to view its contents.
                      </p>
                    </div>
                  ) : fileLoading ? (
                    <div className="code-empty">
                      <div className="code-empty-icon">
                        <Icon name="spinner" size={28} className="spin" />
                      </div>

                      <h3>Loading file</h3>

                      <p>
                        Reading {selectedFile.name}...
                      </p>
                    </div>
                  ) : (
                    <pre>
                      <code>{fileContent}</code>
                    </pre>
                  )}
                </div>
              </section>
            </div>
          </section>
        )}

        {/* =========================
            RUN TELEMETRY
           ========================= */}

        <section className="telemetry" aria-label="Pipeline telemetry">
          <div className="telemetry-header">
            <div>
              <span className="section-kicker">RUN TELEMETRY</span>
              <h2>Engineering progress</h2>
            </div>
            <span className={`telemetry-state telemetry-${status}`}>
              {activeLabel}
            </span>
          </div>

          <div className="telemetry-grid">
            <div className="progress-panel">
              <div className="progress-ring" style={{ "--progress": `${progressPercent * 3.6}deg` }}>
                <div className="progress-ring-inner">
                  <strong>{progressPercent}%</strong>
                  <span>complete</span>
                </div>
              </div>

              <div className="progress-copy">
                <span className="metric-label">PIPELINE COMPLETION</span>
                <strong>{completedStages} / {pipelineSteps.length} stages</strong>
                <p>
                  {status === "generating"
                    ? `Currently working on ${activeLabel}.`
                    : status === "completed"
                      ? "All required engineering stages completed."
                      : status === "failed"
                        ? "The run needs attention before it can complete."
                        : "Start a generation run to track agent progress."}
                </p>
              </div>
            </div>

            <div className="telemetry-track-panel">
              <div className="metric-row">
                <span>Stage flow</span>
                <span>{completedStages} completed</span>
              </div>
              <div className="stage-track">
                {pipelineSteps.map((step) => (
                  <span
                    key={step.id}
                    className={`stage-segment ${pipelineState[step.id]}`}
                    title={`${step.title}: ${pipelineState[step.id]}`}
                  />
                ))}
              </div>
              <div className="telemetry-legend">
                <span><i className="legend-dot done" /> Done</span>
                <span><i className="legend-dot active" /> Active</span>
                <span><i className="legend-dot waiting" /> Waiting</span>
              </div>
            </div>

            <div className="agent-focus-panel">
              <span className="metric-label">ACTIVE AGENT</span>
              <div className="agent-focus">
                <span className="agent-focus-icon">
                  <Icon name={runningStage?.icon || "plan"} size={18} />
                </span>
                <div>
                  <strong>{runningStage?.title || activeLabel}</strong>
                  <span>{status === "generating" ? "Processing request" : "No agent currently running"}</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* =========================
            PIPELINE
           ========================= */}

        <section className="pipeline">
          <div className="section-title">
            <div>
              <span>ENGINEERING PIPELINE</span>
              {status === "generating" && (
                <small className="pipeline-live-label">
                  LIVE · {currentStep.toUpperCase()}
                </small>
              )}
            </div>

            <span className="pipeline-count">
              7 STAGES
            </span>
          </div>

          <div className="pipeline-grid">
            {pipelineSteps.map((step, index) => (
              <div
                key={step.id}
                className="pipeline-node"
              >
                <div
                  className={getStepClass(step.id)}
                  data-state={pipelineState[step.id]}
                >
                  <div className="step-number">
                    {step.number}
                  </div>

                  <div className="step-icon">
                    <Icon name={step.icon} size={19} />
                  </div>

                  <div className="step-status">
                    {pipelineState[step.id] === "running"
                      ? "RUNNING"
                      : pipelineState[step.id] === "completed"
                        ? "DONE"
                        : pipelineState[step.id] === "failed"
                          ? "FAILED"
                          : step.id === "fixer"
                            ? "ON DEMAND"
                            : "WAITING"}
                  </div>

                  <h3>{step.title}</h3>

                  <p>{step.description}</p>
                </div>

                {index < pipelineSteps.length - 1 && (
                  <div
                    className={`pipeline-connector ${pipelineState[step.id] === "completed"
                      ? "connector-completed"
                      : ""
                      }`}
                  >
                    <span />
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>

      </main>

      <footer className="footer">
        <span>DevMate-AI</span>

        <span>
          Agentic Software Engineering Platform
        </span>
      </footer>
    </div>
  );
}

export default App;