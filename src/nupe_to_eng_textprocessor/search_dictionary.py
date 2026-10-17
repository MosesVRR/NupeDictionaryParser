
import sqlite3
from pathlib import Path


# Locate the project root and database.
PROJECT_DIR = Path(__file__).resolve().parents[2]
DATABASE_PATH = PROJECT_DIR / "output" / "nupe_dictionary.sqlite3"


def search_dictionary(connection, query):
    """Find exact headword and alternative-spelling matches."""

    sql = """
        SELECT
            e.entry_id,
            e.headword,
            e.source_printed_page,
            e.review_required,
            e.human_verified,
            s.sense_order,
            s.part_of_speech,
            s.definition_en,
            s.category_code,
            a.information_order,
            a.information,
            alt.spelling
        FROM entries AS e
        LEFT JOIN senses AS s
            ON e.entry_id = s.entry_id
        LEFT JOIN additional_information AS a
            ON e.entry_id = a.entry_id
        LEFT JOIN alternative_spellings AS alt
            ON e.entry_id = alt.entry_id
        WHERE e.headword = ?

        UNION ALL

        SELECT
            e.entry_id,
            e.headword,
            e.source_printed_page,
            e.review_required,
            e.human_verified,
            s.sense_order,
            s.part_of_speech,
            s.definition_en,
            s.category_code,
            a.information_order,
            a.information,
            alt.spelling
        FROM entries AS e
        JOIN alternative_spellings AS search_alt
            ON e.entry_id = search_alt.entry_id
        LEFT JOIN senses AS s
            ON e.entry_id = s.entry_id
        LEFT JOIN additional_information AS a
            ON e.entry_id = a.entry_id
        LEFT JOIN alternative_spellings AS alt
            ON e.entry_id = alt.entry_id
        WHERE search_alt.spelling = ?
          AND e.headword != ?

        ORDER BY headword, sense_order, information_order;
    """

    return connection.execute(
        sql, (query, query, query)
    ).fetchall()


def display_results(rows):
    """Display entries, definitions, notes, and spelling variants."""

    if not rows:
        print("\nNo matching entry found.")
        print("Check the spelling and diacritics, then try again.")
        return

    entries = {}

    for row in rows:
        (
            entry_id,
            headword,
            printed_page,
            review_required,
            human_verified,
            sense_order,
            part_of_speech,
            definition,
            category_code,
            information_order,
            information,
            alternative_spelling,
        ) = row

        if entry_id not in entries:
            entries[entry_id] = {
                "headword": headword,
                "printed_page": printed_page,
                "review_required": bool(review_required),
                "human_verified": bool(human_verified),
                "senses": {},
                "information": {},
                "alternatives": set(),
            }

        entry = entries[entry_id]

        if definition is not None:
            entry["senses"][sense_order] = {
                "part_of_speech": part_of_speech,
                "definition": definition,
                "category_code": category_code,
            }

        if information is not None:
            entry["information"][information_order] = information

        if alternative_spelling:
            entry["alternatives"].add(alternative_spelling)

    for entry in entries.values():
        print("\n" + "=" * 55)
        print(f"Headword: {entry['headword']}")

        if entry["printed_page"] is not None:
            print(f"Printed page: {entry['printed_page']}")

        print(
            "Human verified: "
            + ("Yes" if entry["human_verified"] else "No")
        )

        if entry["review_required"]:
            print("Review status: Review required")
        else:
            print("Review status: No review flagged")

        for order, sense in sorted(entry["senses"].items()):
            print(f"\nSense {order}")

            if sense["part_of_speech"]:
                print(f"Part of speech: {sense['part_of_speech']}")

            print(f"Definition: {sense['definition']}")

            if sense["category_code"]:
                print(f"Category: {sense['category_code']}")

        if entry["information"]:
            print("\nAdditional information:")

            for order, information in sorted(
                entry["information"].items()
            ):
                print(f"  - {information}")

        if entry["alternatives"]:
            print("\nAlternative spellings:")
            print("  " + ", ".join(sorted(entry["alternatives"])))

        print("=" * 55)


def main():
    if not DATABASE_PATH.exists():
        print(f"Database not found: {DATABASE_PATH}")
        print("Check the database location.")
        return

    try:
        # Open the database in read-only mode.
        database_uri = DATABASE_PATH.as_uri() + "?mode=ro"

        with sqlite3.connect(database_uri, uri=True) as connection:
            print("Nupe-to-English Dictionary")
            print("Search by exact headword or alternative spelling.")
            print("Type 'q' or 'quit' to exit.")

            while True:
                query = input("\nSearch: ").strip()

                if query.casefold() in {"q", "quit"}:
                    print("Goodbye!")
                    break

                if not query:
                    continue

                rows = search_dictionary(connection, query)
                display_results(rows)

    except sqlite3.Error as error:
        print(f"Database error: {error}")


if __name__ == "__main__":
    main()
