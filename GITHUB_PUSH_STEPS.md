# Push LUMO22 to GitHub (then deploy)

Your project is already a git repo with one commit. Do these steps once.

---

## 1. Create a GitHub account (if you don’t have one)

1. Go to [github.com](https://github.com) and click **Sign up**.
2. Enter email, password, username. Verify your email.
3. You’re in.

---

## 2. Create a new repo on GitHub

1. Click the **+** (top right) → **New repository**.
2. **Repository name:** `LUMO22` (or any name you like).
3. Leave it **Public**. Don’t add a README, .gitignore, or license (you already have them).
4. Click **Create repository**.

---

## 3. Connect your folder and push

GitHub will show “push an existing repository from the command line”. In Terminal on your Mac, run (replace `YOUR_USERNAME` with your GitHub username):

```bash
cd /Users/sophieoverment/LUMO22
git remote add origin https://github.com/YOUR_USERNAME/LUMO22.git
git branch -M main
git push -u origin main
```

When it asks for your GitHub username and password: use your **username** and a **Personal Access Token** (GitHub no longer accepts account passwords for push). To create a token: GitHub → Settings → Developer settings → Personal access tokens → Generate new token; give it “repo” scope, copy it, and paste it when git asks for a password.

---

## 4. Deploy

Open **DEPLOY_TO_LIVE.md** and follow Option A (Railway) or Option B (Render). Connect the repo you just pushed; the host will build and run your app.

---

Your `.env` is not in the repo (it’s in .gitignore). Add the same variables in the host’s dashboard (Railway or Render) when you deploy.
