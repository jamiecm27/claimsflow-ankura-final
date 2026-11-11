# ClaimsFlow
## AI-Assisted Insurance Claims Workbench

**Ankura AI Advisory | Prototype Assessment | November 2026**

**Developed and adapted by:** Jamie Campbell-Mooney  
**Project status:** Private, non-commercial proof of concept  
**Original project attribution:** Sanket Barde

---

## 1. Project Overview

ClaimsFlow is an interactive AI-assisted insurance claims processing prototype developed for the Ankura AI Advisory assessment.

The application explores how artificial intelligence can support insurance claims processing, improve operational efficiency, reduce handling costs and assist human decision-making.

ClaimsFlow provides a practical demonstration of how insurance organisations might integrate AI into existing claims workflows while maintaining appropriate human oversight.

The prototype enables users to compare traditional human-only claims processing with AI-assisted workflows, evaluate AI-generated recommendations and examine potential operational benefits.

**ClaimsFlow is a demonstration and evaluation tool, not a production insurance claims management system.**

## 2. Project Objectives

The prototype was developed to investigate five questions:

1. How can AI support the extraction, analysis and routing of insurance claims?
2. Can AI-assisted processing reduce the time required to handle claims?
3. What potential cost savings could be achieved through AI-assisted workflows?
4. How accurately can AI recommend appropriate claims routing decisions?
5. How can insurers balance automation with human oversight?

The application provides an interactive environment in which these questions can be explored using synthetic claims, configurable assumptions and AI-assisted processing.

## 3. Application Features

### 3.1 Claims Inbox

The Claims Inbox provides the main interface for reviewing and processing insurance claims.

Features include:

- Viewing and selecting insurance claims.
- Examining claim information and supporting details.
- Comparing human-only and AI-assisted processing approaches.
- Reviewing AI-generated extraction and routing recommendations.
- Identifying claims requiring additional review.
- Supporting human oversight of AI recommendations.

The Claims Inbox demonstrates how AI could be integrated into a claims handler's existing workflow rather than operating as a completely independent decision-making system.

### 3.2 AI Prototype Testing

The AI Prototype Testing environment enables users to evaluate the potential operational impact of AI-assisted claims processing.

Features include:

- Selecting claims for prototype testing.
- Comparing simulated human processing with AI-assisted processing.
- Executing AI-assisted analysis using Google Gemini.
- Reviewing claims routing recommendations.
- Comparing estimated processing times.
- Comparing estimated handling costs.
- Exploring routing accuracy and workflow outcomes.
- Distinguishing simulated results from actual AI outputs.

**Evaluation methodology**

The prototype distinguishes between three types of information:

**Simulated human processing:** Estimates based on defined assumptions about traditional claims handling.

**AI-assisted processing:** Results produced through the prototype's AI-supported workflow, including Gemini-generated outputs where configured.

**Actual human assessments:** Real human review results, which must be entered or collected separately rather than being presented as measured results when no review has occurred.

This distinction is important to ensure that simulated performance is not confused with independently validated operational evidence.

### 3.3 Administration

The Administration interface supports the configuration and demonstration of ClaimsFlow.

Features include:

- Importing synthetic insurance claims.
- Preparing datasets for prototype testing.
- Supporting bulk import of up to 100 synthetic claims.
- Managing assumptions used in workflow comparisons.
- Preparing repeatable demonstration scenarios.

The administration functionality enables the prototype to demonstrate how AI-assisted processing might perform across a larger claims workload rather than through isolated examples.

## 4. Technology Stack

### Frontend

- React
- Vite
- JavaScript
- CSS
- Supporting React interface libraries

### Backend

- Python
- FastAPI
- Google Gemini API
- JSON-based data storage
- Supporting Python libraries for claims processing

### Development Environment

- macOS
- Visual Studio Code or equivalent editor
- Git and GitHub
- Local Python and Node.js environments

### AI Integration

Google Gemini is used to support AI-based claims analysis, extraction and routing recommendations.

The application requires a valid Gemini API key for live AI functionality.

Any rule-based or simulated fallback behaviour should be distinguished from successful live AI processing.

## 5. Claims Processing Workflow

ClaimsFlow demonstrates the following conceptual workflow:

**Step 1 — Claim selection**

A user selects an insurance claim from the Claims Inbox or prototype testing interface.

**Step 2 — Claim analysis**

The application examines available claim information and, where configured, uses AI to support information extraction and analysis.

**Step 3 — Validation**

Relevant claim details are assessed for completeness and potential issues requiring further review.

**Step 4 — Routing recommendation**

The application generates or presents a recommended claims handling route.

**Step 5 — Human oversight**

The claims handler can review the recommendation and determine whether further investigation, specialist assessment or manual intervention is appropriate.

**Step 6 — Performance evaluation**

The testing environment compares workflow assumptions and AI-assisted outcomes to explore potential differences in handling time, cost and decision quality.

## 6. Human-Only vs AI-Assisted Processing

A central feature of ClaimsFlow is its ability to compare two approaches to insurance claims handling.

| Dimension | Human-only workflow | AI-assisted workflow |
|---|---|---|
| Information review | Manual examination | AI-supported analysis |
| Data extraction | Manual identification | AI-assisted extraction |
| Claims routing | Human assessment | AI-generated recommendation with human oversight |
| Processing time | Simulated baseline | AI workflow timing or estimates, as labelled |
| Handling cost | Assumption-based estimate | Assumption-based estimate |
| Decision quality | Requires human review evidence | Requires validation against reference decisions |

The comparison is designed to support discussion about the potential benefits, limitations and implementation considerations of AI in insurance operations.

The prototype does not establish that AI is universally faster, cheaper or more accurate than human claims handlers.

## 7. Prototype Data and Evaluation

ClaimsFlow uses synthetic insurance claims for demonstration and testing.

Synthetic datasets allow different claim types and processing scenarios to be evaluated without requiring real customer information.

The prototype supports comparisons involving:

- Claims processing time.
- Estimated handling cost.
- AI routing recommendations.
- Human review requirements.
- Potential efficiency improvements.
- Operational trade-offs between automation and human oversight.

### Important Evaluation Limitations

Simulated human handling times and costs are assumptions, not independently measured operational performance.

AI-generated results require validation against appropriate reference outcomes before claims about accuracy or business performance can be substantiated.

The prototype's outputs should therefore be interpreted as exploratory findings rather than production-ready performance evidence.

## 8. Installation and Local Setup

ClaimsFlow consists of a React frontend and a FastAPI backend.

### Prerequisites

The following software is required:

- Node.js and npm.
- Python and pip.
- Git, if cloning from GitHub.
- A Gemini API key for live AI functionality.

### 8.1 Obtain the Project

Clone the private repository using an authorised GitHub account:

```bash
git clone https://github.com/jamiecm27/claimsflow-ankura-final.git
cd claimsflow-ankura-final
```

Alternatively, download the project ZIP from GitHub and extract it locally.

### 8.2 Configure the Backend

Navigate to the backend directory:

```bash
cd backend
```

Create a Python virtual environment:

```bash
python3 -m venv .venv
```

Activate it on macOS:

```bash
source .venv/bin/activate
```

Install the required Python dependencies:

```bash
python -m pip install -r requirements.txt
```

### 8.3 Configure Gemini

Create a local environment configuration file from the supplied example, if present:

```bash
cp .env.example .env
```

Edit `backend/.env` and add a valid Gemini API key:

```dotenv
GEMINI_API_KEY=your_gemini_api_key
```

Additional environment settings may be required depending on the current backend configuration.

**Security:** Never upload `.env`, API keys, credentials or other secrets to GitHub.

### 8.4 Start the Backend

From the backend directory, with the virtual environment activated:

```bash
python -m uvicorn app:app --reload
```

The default local backend address is:

http://127.0.0.1:8000

FastAPI documentation, where enabled, is available at:

http://127.0.0.1:8000/docs

### 8.5 Start the Frontend

Open a second Terminal window.

Navigate to the project root and install the frontend dependencies:

```bash
npm install
```

Start the development server:

```bash
npm run dev
```

The default frontend address is:

http://localhost:5173

The actual address may differ if the configured port is already in use.

### 8.6 macOS Launcher

The project includes a `start_claimsflow.command` launcher intended to simplify local startup.

After installing the required dependencies, macOS users may launch the application through this script.

Python virtual environments are machine-specific. When moving the project between Macs, each computer should create its own environment rather than relying on a copied `.venv` directory.

The launcher and its configuration may need adjustment for the local installation path.

## 9. Security and Data Handling

ClaimsFlow is a prototype and has not been designed or certified for production use.

The following restrictions apply:

- Use synthetic or appropriately authorised test data.
- Do not upload real customer claims or sensitive personal information without suitable controls.
- Keep Gemini API credentials outside version control.
- Restrict repository access to authorised collaborators.
- Do not assume that prototype outputs are suitable for automated insurance decisions.
- Do not expose the development backend directly to the public internet without appropriate security controls.

Production deployment would require additional work covering authentication, authorisation, data protection, logging, monitoring, security testing and operational resilience.

## 10. Prototype Limitations

ClaimsFlow is intended to demonstrate a potential AI-enabled claims handling approach.

Current limitations include:

- Reliance on synthetic claims and simulated operational assumptions.
- Limited evidence of real-world processing performance.
- AI outputs that may be inaccurate or incomplete.
- No independently established production-level routing accuracy.
- No validated production fraud detection capability.
- No assurance of compliance with insurer-specific operational requirements.
- Development-oriented architecture rather than a hardened production deployment.

These limitations should be considered when interpreting the prototype's outputs.

## 11. Potential Future Development

Possible extensions include:

- Integration with real insurance claims management systems.
- Structured human review and feedback capture.
- Larger-scale evaluation against independently labelled claims.
- Improved document processing and OCR.
- More detailed cost and productivity modelling.
- Authentication and role-based access controls.
- Centralised data storage for multi-user collaboration.
- Monitoring and audit trails for AI recommendations.
- Production-oriented security and deployment architecture.
- Model performance monitoring and governance controls.

## 12. Author and Acknowledgements

### ClaimsFlow Development

**Jamie Campbell-Mooney**

Developer of the adapted and extended ClaimsFlow insurance claims workbench.

Developed for the Ankura AI Advisory prototype assessment, November 2026.

### Original Project Attribution

ClaimsFlow builds upon the original **AI-Based Insurance Claim Extraction & Routing Agent** developed by **Sanket Barde**.

Original GitHub repository:

https://github.com/SANKETBARDE/FNOL_Claim_Extraction

Sanket Barde's original project provided a technical foundation for insurance document extraction, validation, claims routing and elements of the React/FastAPI application architecture.

Jamie Campbell-Mooney subsequently adapted and extended this foundation into the ClaimsFlow workbench, adding functionality focused on human-versus-AI workflow comparisons, prototype testing, synthetic claims evaluation, operational performance analysis and administration.

**Full acknowledgement and credit are given to Sanket Barde for his original work.**

Copyright in the original code remains with its respective copyright holder. Jamie Campbell-Mooney does not claim ownership of Sanket Barde's original contributions.

The original repository does not appear to provide an explicit software licence. This attribution does not itself grant permission to reproduce, modify or redistribute the original code.

## 13. Private Prototype Notice

**Project classification: Private, non-commercial educational and assessment prototype.**

ClaimsFlow has been prepared for demonstration, learning and evaluation in connection with the Ankura AI Advisory assessment.

The repository is intended to remain private and accessible only to authorised collaborators.

It is not intended for public distribution, commercial deployment or use in live insurance claims processing.

Private or non-commercial status does not override third-party copyright or software licensing requirements. Permission may be needed for continued reuse or redistribution of original third-party code.

---

**ClaimsFlow | Jamie Campbell-Mooney | November 2026**

*AI-Assisted Insurance Claims Workbench — Private Proof of Concept*
