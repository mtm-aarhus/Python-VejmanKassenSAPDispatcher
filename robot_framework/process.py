"""This module contains the main process of the robot."""

from OpenOrchestrator.orchestrator_connection.connection import OrchestratorConnection
from OpenOrchestrator.database.queues import QueueElement
import pyodbc
import json

# pylint: disable-next=unused-argument
def process(orchestrator_connection: OrchestratorConnection, queue_element: QueueElement | None = None) -> None:
    """Do the primary process of the robot."""
    orchestrator_connection.log_trace("Running process.")
    sql_server = orchestrator_connection.get_constant("SqlServer").value
    conn_string = "DRIVER={SQL Server};"+f"SERVER={sql_server};DATABASE=VejmanKassen;Trusted_Connection=yes;"
    conn = pyodbc.connect(conn_string)
    cursor = conn.cursor()

    # --- 1) Claim rows atomically (Afsendt -> Claimed) and fetch them ---
    # Use UPDLOCK + READPAST so concurrent workers don't claim the same rows.
    claim_sql = """
    UPDATE v
    SET FakturaStatus = 'Claimed'
    OUTPUT inserted.ID, inserted.VejmanID, inserted.Tilladelsesnr
    FROM [VejmanKassen].[dbo].[VejmanFakturering] v WITH (UPDLOCK, READPAST, ROWLOCK)
    WHERE v.FakturaStatus = 'Afsendt';
    """

    # Keep the claim transaction short
    conn.autocommit = False
    cursor.execute(claim_sql)
    rows = cursor.fetchall()
    conn.commit()

    if not rows:
        orchestrator_connection.log_trace("No 'Afsendt' rows to process.")
        return

    # --- 2) Build bulk queue elements payload ---
    # Queue elements: ID + (VejmanID or 'Henstilling') + Tilladelsesnr
    references = []
    data = []

    for r in rows:
        queue_id = r.VejmanID if r.VejmanID is not None else "Henstilling"
        tilladelsesnr = r.Tilladelsesnr

        payload = {
            "ID": r.ID,
            "VejmanID": queue_id,
            "Tilladelsesnr": tilladelsesnr,
        }

        references.append(str(r.ID))
        data.append(json.dumps(payload, ensure_ascii=False))

    # --- 3) Bulk create queue elements ---
    orchestrator_connection.bulk_create_queue_elements(
        "VejmanKassenSAP",
        references=tuple(references),
        data=tuple(data),
    )
    
    # --- 4) Bulk update ONLY claimed IDs to TilFakturering ---
    conn.autocommit = False
    cursor = conn.cursor()

    cursor.execute("CREATE TABLE #ClaimedIds (ID int NOT NULL PRIMARY KEY);")
    cursor.executemany(
        "INSERT INTO #ClaimedIds (ID) VALUES (?);",
        [(r.ID,) for r in rows],
    )

    cursor.execute("""
        UPDATE v
        SET FakturaStatus = 'TilFakturering'
        FROM [VejmanKassen].[dbo].[VejmanFakturering] v
        INNER JOIN #ClaimedIds c ON c.ID = v.ID
        WHERE v.FakturaStatus = 'Claimed';
    """)


    conn.commit()
    conn.close()
    orchestrator_connection.log_trace(
        f"Processed {len(rows)} rows: Claimed -> queue -> TilFakturering."
    )
