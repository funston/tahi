# Octo BIRD Tiny Grounding Stats

- Tasks evaluated: 10
- Tasks with inferred gold tables: 10
- Average table recall: 0.95

## Lowest Recall Tasks

- `cs_semester_0006` (cs_semester): recall=0.5
 - Question: How many research assistants does Sauveur Skyme have?
 - Gold tables: RA, prof
 - Candidate tables: registration, ra
- `cs_semester_0001` (cs_semester): recall=1.0
 - Question: Which course is more difficult, Intro to BlockChain or Computer Network?
 - Gold tables: course
 - Candidate tables: course, registration
- `cs_semester_0002` (cs_semester): recall=1.0
 - Question: Please list the names of the courses that are less important than Machine Learning Theory.
 - Gold tables: course
 - Candidate tables: student, prof, course, ra, registration
- `cs_semester_0003` (cs_semester): recall=1.0
 - Question: How many professors are more popular than Zhou Zhihua?
 - Gold tables: prof
 - Candidate tables: prof
- `cs_semester_0004` (cs_semester): recall=1.0
 - Question: What is the phone number of Kerry Pryor?
 - Gold tables: student
 - Candidate tables: student, prof, ra
