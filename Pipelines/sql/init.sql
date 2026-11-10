-- Runs once when the Postgres volume is first created.
-- Airflow keeps its metadata in "airflow"; the pipeline writes to "warehouse".
CREATE DATABASE airflow;
CREATE DATABASE warehouse;
