import { useState } from "react";
import "./App.css";

const API_BASE_URL = "http://127.0.0.1:8080";

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
      icon: "✦",
      title: "Planner",
      description: "Turns your request into an actionable engineering plan.",
    },
    {
      id: "coder",
      number: "02",
      icon: "</>",
      title: "Coder",
      description: "Generates the project structure and source code.",
    },
    {
      id: "validator",
      number: "03",
      icon: "◈",
      title: "Validator",
      description: "Checks files, imports, dependencies, and structure.",
    },
    {
      id: "reviewer",
      number: "04",
      icon: "◎",
      title: "Reviewer",
      description: "Reviews the implementation against your request.",
    },
    {
      id: "mcp",
      number: "05",
      icon: "⌘",
      title: "MCP Writer",
      description: "Creates and writes the generated files to disk.",
    },
    {
      id: "executor",
      number: "06",
      icon: "▶",
      title: "Executor",
      description: "Runs the generated project and checks runtime behavior.",
    },
    {
      id: "fixer",
      number: "07",
      icon: "⚙",
      title: "Fixer",
      description: "Diagnoses runtime issues and applies targeted fixes.",
    },
  ];


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
            <span>✦</span>
            AI SOFTWARE ENGINEERING AGENT
          </div>

          <h1>
            Build software with
            <span> intelligent agents.</span>
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
                {status === "generating" ? "⋯" : "→"}
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
              {status === "completed" ? "✓" : "!"}
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
                  <span>↓</span>
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
                        /
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
                          {file.name.startsWith(".")
                            ? "•"
                            : "◇"}
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
                        {"</>"}
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
                        ⋯
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
                    {step.icon}
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