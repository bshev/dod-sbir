# DoD SBIR Scraper

Scrapes open DoD SBIR/STTR solicitation topics from dodsbirsttr.mil and stores
them in a local SQLite database. Fetches topic stubs and per-topic details via
the public API, strips HTML from text fields, and upserts into `dod_sbir.db`.

## Setup (Ubuntu Server)

### Install Python 3.13

```bash
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.13 python3.13-venv
```

### Install Poetry

```bash
curl -sSL https://install.python-poetry.org | python3 -
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### Install dependencies

```bash
poetry install --without dev
```

### Run

```bash
poetry run python main.py
```

## Local Workflow

### Pull latest database from server

Requires SSH access to the server where the scraper runs. Configure `.env` first (copy from `.env.example`):

Then pull:

```bash
./pull_db.sh
```

This overwrites `dod_sbir.db` locally without changing `scores.db` 

### Visualizer

```bash
poetry run python viz/app.py
```

## Cron Setup (Ubuntu Server)

1. Fill in `.env` on the server (`PROJECT_DIR` and `POETRY`):

   ```bash
   cp .env.example .env
   # PROJECT_DIR: absolute path to this repo on the server
   # POETRY: output of `which poetry`
   ```

2. Make the script executable:

   ```bash
   chmod +x run_scraper.sh
   ```

3. Open the crontab:

   ```bash
   crontab -e
   ```

4. Add this line to run daily at 6 AM server time (adjust path as needed):

   ```
   0 6 * * * /home/user/dod-sbir/run_scraper.sh
   ```
