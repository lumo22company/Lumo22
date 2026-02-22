# GitHub setup — connect your project

Your project already has git initialized. Follow these steps to push it to GitHub:

## 1. Create a GitHub account (if needed)

Go to [github.com](https://github.com) and sign up.

## 2. Create a new repository

1. Click the **+** in the top right → **New repository**
2. Name it (e.g. `Lumo22` or `lumo22-app`)
3. **Do not** initialise with a README, .gitignore, or licence
4. Click **Create repository**

## 3. Connect and push from Terminal

Copy the commands GitHub shows (they’ll look like this, with your username and repo name):

```bash
cd /Users/sophieoverment/LUMO22
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
git branch -M main
git push -u origin main
```

Replace `YOUR_USERNAME` and `YOUR_REPO_NAME` with your actual GitHub username and repo name.

## 4. Connect to Railway

1. In **Railway** → your project → **Settings**
2. Under **Source**, connect your GitHub repo (or reconnect if it’s already linked)
3. Future deploys will run automatically when you push

## After setup

When you make changes, run:

```bash
git add .
git commit -m "Describe your change"
git push
```

Railway will redeploy automatically if it’s connected to GitHub.
