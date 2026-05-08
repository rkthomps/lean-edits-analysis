import streamlit as st
import subprocess
import logging
import time
import threading

logger = logging.getLogger(__name__)

BUCKET_NAME = "programming-vacuum"
SYNC_TIME_SECONDS = 60 * 60  # Sync every hour.


def sync_thread(sync_time_seconds: int):
    """
    Sync the local data with the S3 bucket.
    """
    while True:
        logger.info("Starting sync...")
        try:
            subprocess.run(["./sync.sh"], check=True, capture_output=True, text=True)
            logger.info("Sync completed successfully.")
        except subprocess.CalledProcessError as e:
            logger.error(f"Sync failed: {e}")
        time.sleep(sync_time_seconds)


@st.cache_resource
def start_sync_thread():
    """
    Start the sync thread.
    """
    thread = threading.Thread(
        target=sync_thread, args=(SYNC_TIME_SECONDS,), daemon=True
    )
    thread.start()
    return thread


def main():
    st.title("Hello, World!")
    st.write("Welcome to lean-edits-dashboard!")

    start_sync_thread()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("app.log"),
        ],
    )
    main()
