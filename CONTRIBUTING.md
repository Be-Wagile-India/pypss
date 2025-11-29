# 🤝 Contributing to pypss

First off, thank you for considering contributing to `pypss`! It's people like you that make this tool better.

By participating in this project, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).

## 📚 Table of Contents
- [How to Contribute](#how-to-contribute)
  - [1. Fork & Clone](#1-fork--clone)
  - [2. Environment Setup](#2-environment-setup)
  - [3. Development Workflow](#3-development-workflow)
  - [4. Submit a Pull Request](#4-submit-a-pull-request)
- [Reporting Bugs](#reporting-bugs)
- [Feature Requests](#feature-requests)

---

## How to Contribute

### 1. Fork & Clone
1.  **Fork** the [pypss repository](https://github.com/Be-Wagile-India/pypss) to your GitHub account.
2.  **Clone** your fork to your local machine:
    ```bash
    git clone https://github.com/your-username/pypss.git
    cd pypss
    ```

### 2. Environment Setup
We recommend using a virtual environment. We also use `Makefile` to simplify setup.

```bash
# Create venv and install dependencies
make install
```
*This command installs the package in editable mode along with `dev` and `docs` dependencies and sets up pre-commit hooks.*

### 3. Development Workflow

1.  **Create a Branch:**
    ```bash
    git checkout -b feature/amazing-feature
    ```

2.  **Make Changes:** Write your code and tests.

3.  **Ensure Quality:**
    Use our `make` commands to keep your code clean and working.
    *   `make lint-fix`: Auto-fix style issues (using Ruff).
    *   `make test`: Run the test suite.
    *   `make check`: Run **everything** (lint, type-check, test) - *Recommended before committing*.

### 4. Submit a Pull Request
1.  Commit your changes with a clear message:
    ```bash
    git commit -m "feat: Add support for concurrency metrics"
    ```
2.  Push to your fork:
    ```bash
    git push origin feature/amazing-feature
    ```
3.  Open a **Pull Request** on the main repository.

---

## 🐛 Reporting Bugs
Found a bug? Please open an issue on our [Issue Tracker](https://github.com/Be-Wagile-India/pypss/issues).
Include:
- Steps to reproduce.
- Expected vs. actual behavior.
- Your environment details (OS, Python version).

## 💡 Feature Requests
Have an idea? We'd love to hear it! Open a [Feature Request](https://github.com/Be-Wagile-India/pypss/issues) and describe what you want to build.