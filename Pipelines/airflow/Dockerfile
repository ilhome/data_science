FROM apache/airflow:3.0.6-python3.11

# The pipeline package runs in-process inside Airflow tasks (TaskFlow), so its
# dependencies are installed next to Airflow's own. They are all compatible
# with the image's pinned versions; see requirements.txt.
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
