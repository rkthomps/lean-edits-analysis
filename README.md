# LeanEdits Dashboard
A dashboard for displaying the data collected by [LeanEdits](https://github.com/rkthomps/lean-edits)

## Setup
```bash
uv sync

# Perform an initial sync with the database. 
# Useful for ensuring credentials.
bash check-setup.sh 
```

## Running the Dashboard 
```bash
streamlit run main.py --server.address localhost 
```