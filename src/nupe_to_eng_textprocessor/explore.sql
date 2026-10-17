-- SQLite

-- SELECT name
-- FROM sqlite_master
-- WHERE type = 'table'
-- ORDER BY name;


-- PRAGMA table_info(senses);


-- PRAGMA table_info(senses);


-- SELECT
--     e.headword,
--     s.sense_order,
--     s.part_of_speech,
--     s.definition_en,
--     s.category_code,
--     e.source_printed_page
-- FROM entries AS e
-- JOIN senses AS s
--     ON e.entry_id = s.entry_id
-- WHERE e.headword = 'áyíbì'
-- ORDER BY s.sense_order;



-- SELECT
--     e.headword,
--     COUNT(s.sense_id) AS number_of_senses
-- FROM entries AS e
-- LEFT JOIN senses AS s
--     ON e.entry_id = s.entry_id
-- GROUP BY e.entry_id, e.headword
-- ORDER BY e.headword
-- LIMIT 30;



-- SELECT headword
-- FROM entries
-- WHERE headword LIKE 'à%'
-- ORDER BY headword
-- LIMIT 50;

PRAGMA table_info(additional_information);

