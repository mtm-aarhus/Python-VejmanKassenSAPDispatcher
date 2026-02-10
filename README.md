# VejmanKassen SAP Dispatcher

## Purpose

This process collects all fakturering rows marked as **`Afsendt`**, safely claims them to avoid double processing, creates queue elements for further processing, and finally marks the rows as **`TilFakturering`**.

The process is designed to be safe if multiple robot instances run at the same time.

---

## High-level flow

1. **Claim rows**

   * All rows with `FakturaStatus = 'Afsendt'` are atomically updated to `Claimed`.
   * The claimed rows are returned in the same operation.
   * SQL locking ensures that two parallel runs cannot claim the same rows.

2. **Prepare queue data**

   * For each claimed row, a JSON payload is created containing:

     * `ID`
     * `VejmanID` (or `"Henstilling"` if `VejmanID` is `NULL`)
     * `Tilladelsesnr`
   * Each row ID is used as the queue reference.

3. **Bulk create queue elements**

   * All payloads are sent in one call using bulk queue creation.

4. **Finalize rows**

   * Only the rows claimed in this run are updated from `Claimed` to `TilFakturering`.
   * A SQL temporary table is used to precisely target the claimed rows.

5. **Cleanup**

   * The database transaction is committed and the connection is closed.
   * Temporary tables are automatically removed when the connection closes.

---

## Concurrency guarantees

* Rows are claimed using a single atomic SQL statement.
* `UPDLOCK` and `READPAST` prevent multiple processes from claiming the same row.
* Each run only finalizes rows it has claimed itself.

---

## Status lifecycle

| Status           | Meaning                               |
| ---------------- | ------------------------------------- |
| `Afsendt`        | Ready to be picked up by the process  |
| `Claimed`        | Temporarily reserved by a running job |
| `TilFakturering` | Successfully queued for next step     |

---

## Notes

* The process always handles **all available `Afsendt` rows** at the time it runs.
* Temporary SQL tables are session-scoped and automatically dropped when the connection closes.
* If no rows are found, the process exits without doing any work.


# Robot-Framework V4

This repo is meant to be used as a template for robots made for [OpenOrchestrator](https://github.com/itk-dev-rpa/OpenOrchestrator) v2.

## Quick start

1. To use this template simply use this repo as a template (see [Creating a repository from a template](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-repository-from-a-template)).
__Don't__ include all branches.

2. Go to `robot_framework/__main__.py` and choose between the linear framework or queue based framework.

3. Implement all functions in the files:
    * `robot_framework/initialize.py`
    * `robot_framework/reset.py`
    * `robot_framework/process.py`

4. Change `config.py` to your needs.

5. Fill out the dependencies in the `pyproject.toml` file with all packages needed by the robot.

6. Feel free to add more files as needed. Remember that any additional python files must
be located in the folder `robot_framework` or a subfolder of it.

When the robot is run from OpenOrchestrator the `main.py` file is run which results
in the following:

1. The working directory is changed to where `main.py` is located.
2. A virtual environment is automatically setup with the required packages.
3. The framework is called passing on all arguments needed by [OpenOrchestrator](https://github.com/itk-dev-rpa/OpenOrchestrator).

## Requirements

Minimum python version 3.11

## Flow

This framework contains two different flows: A linear and a queue based.
You should only ever use one at a time. You choose which one by going into `robot_framework/__main__.py`
and uncommenting the framework you want. They are both disabled by default and an error will be
raised to remind you if you don't choose.

### Linear Flow

The linear framework is used when a robot is just going from A to Z without fetching jobs from an
OpenOrchestrator queue.
The flow of the linear framework is sketched up in the following illustration:

![Linear Flow diagram](Robot-Framework.svg)

### Queue Flow

The queue framework is used when the robot is doing multiple bite-sized tasks defined in an
OpenOrchestrator queue.
The flow of the queue framework is sketched up in the following illustration:

![Queue Flow diagram](Robot-Queue-Framework.svg)

## Linting and Github Actions

This template is also setup with flake8 and pylint linting in Github Actions.
This workflow will trigger whenever you push your code to Github.
The workflow is defined under `.github/workflows/Linting.yml`.
