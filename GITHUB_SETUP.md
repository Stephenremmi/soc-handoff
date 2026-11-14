# GitHub setup after the localhost demo

This guide starts from the repo-ready SOC Handoff project folder. Follow the README to bring over your local settings and verify the app first.

## First verify localhost

Start the tracker in your activated Git Bash terminal.

```bash
python -m uvicorn tracker:app --host 127.0.0.1 --port 8001
```

Start the app in a second Git Bash terminal in the same folder.

```bash
source .venv/Scripts/activate
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Open [localhost](http://127.0.0.1:8000) and sign in with SOC_DEMO_USER and SOC_DEMO_PASSWORD. Propose a follow-up and execute before approval to see Blocked. Approve it, execute again, and verify the ticket. Roll it back to confirm closure.

## Create and push the GitHub repository

After the demo works, create an empty private GitHub repository named soc-handoff. Leave GitHub's README, .gitignore, and license options unselected since the project already has files. For a new local Git repository, run the following from the project folder.

```bash
git init -b main
git check-ignore -v .env .venv/ tracker.sqlite3
git add -- .gitignore .env.example README.md GITHUB_SETUP.md AGENTS.md app.py tracker.py requirements.txt setup_demo.py soc_handoff sandbox_tracker scripts docs .github/workflows/ci.yml tests
git diff --cached --name-only
git commit -m "Add SOC Handoff audit MVP and integration CI"
```

Review the staged list before committing. It should include .env.example and omit .env. Copy your repository's HTTPS URL and use it in this command.

```bash
git remote add origin https://github.com/YOUR-ACCOUNT/soc-handoff.git
git push -u origin main
```

If this folder already has a Git repository, inspect `git status` and `git remote -v` before changing the branch or adding a remote.

## Verify GitHub Actions and open in Codex

In GitHub, open **Actions → SOC Handoff CI**. The workflow runs for pushes and pull requests. Each run starts temporary MongoDB, seeds the synthetic records, and tests both services with separate databases. It does not require Atlas credentials and has no deployment step.

Open the repository root in Codex or select the private repo when setting up Codex's GitHub access. AGENTS.md provides the project context. You can start with this prompt:

> Read AGENTS.md and README.md. Trace an approved follow-up from the browser through the Atlas policy check to the sandbox tracker. Use the automated smoke test as the baseline for any change.

A future deployment workflow needs a deployment target and separate runtime credentials.
