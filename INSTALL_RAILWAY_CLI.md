# Install Railway CLI (Step 2 — do this yourself)

Your Mac doesn’t have Homebrew or Node, and the Railway install script needs your Mac password. Run **one** of the options below in **Terminal** on your Mac.

---

## Option A: Install script (quick)

1. Open **Terminal** (Spotlight: type `Terminal`, press Enter).
2. Paste and run:
   ```bash
   curl -fsSL https://raw.githubusercontent.com/railwayapp/cli/master/install.sh | sh
   ```
3. When it asks for your **Mac login password**, type it and press Enter (nothing will show as you type).
4. When it finishes, run `railway --version` to confirm. Then go to **Step 3** in **DEPLOY_TO_LIVE.md** (Option C).

---

## Option B: Install Homebrew, then Railway

1. Open **Terminal**. Paste and run (from [brew.sh](https://brew.sh)):
   ```bash
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```
   Enter your Mac password when asked. Wait for it to finish.

2. Then run:
   ```bash
   brew install railway
   ```

3. Run `railway --version`. Then do **Step 3** in **DEPLOY_TO_LIVE.md** (Option C).

---

## Option C: Download the binary (no password, no Homebrew)

1. Go to [github.com/railwayapp/cli/releases](https://github.com/railwayapp/cli/releases).
2. Download the latest **macOS** file:
   - **Apple Silicon (M1/M2/M3):** `railway-*-aarch64-apple-darwin.tar.gz`
   - **Intel Mac:** `railway-*-x86_64-apple-darwin.tar.gz`
3. Double-click the `.tar.gz` to unpack it. You’ll get a file named `railway`.
4. Move it somewhere in your PATH or use it by full path, e.g.:
   ```bash
   mkdir -p ~/bin
   mv railway ~/bin/
   chmod +x ~/bin/railway
   ```
   Then add `~/bin` to your PATH (in `~/.zshrc` add a line: `export PATH="$HOME/bin:$PATH"`), open a new Terminal, and run `railway --version`.

---

After Railway CLI is installed, continue with **Step 3** in **DEPLOY_TO_LIVE.md** (Option C): `cd` to LUMO22, `railway login`, `railway init`, `railway up`.
