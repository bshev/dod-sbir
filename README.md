# DoD SBIR Scraper

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
