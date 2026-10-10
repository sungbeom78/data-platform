-- 스모크 테스트: 샘플 데이터 투입 후 업무 규칙이 제약으로 막히는지 확인. 마지막에 ROLLBACK.
BEGIN;
INSERT INTO acad.department (dept_cd, dept_nm) VALUES ('D01','컴퓨터공학과'),('D02','통계학과');
INSERT INTO acad.professor (prof_no) VALUES ('P01'),('P02'),('P03');
INSERT INTO acad.pi_professor SELECT prof_id, v.nm, now(), now() FROM acad.professor p JOIN (VALUES ('P01','박서연'),('P02','이현우'),('P03','최지훈')) v(no,nm) ON v.no=p.prof_no;
INSERT INTO acad.student (stud_no, dept_id) SELECT v.no, d.dept_id FROM (VALUES ('S001','D01'),('S002','D01'),('S003','D02')) v(no,dc) JOIN acad.department d ON d.dept_cd=v.dc;
INSERT INTO acad.pi_student SELECT s.stud_id, v.nm, now(), now() FROM acad.student s JOIN (VALUES ('S001','김민준'),('S002','이서윤'),('S003','박하준')) v(no,nm) ON v.no=s.stud_no;
INSERT INTO acad.course (course_cd, course_nm, credit, prof_id) SELECT v.cd, v.nm, v.cr, p.prof_id FROM (VALUES ('C101','데이터베이스',3,'P01'),('C102','자료구조',3,'P02'),('C201','통계기초',2,'P03')) v(cd,nm,cr,pn) JOIN acad.professor p ON p.prof_no=v.pn;
INSERT INTO acad.enrollment (stud_id, course_id, grade_cd) SELECT s.stud_id, c.course_id, v.g FROM (VALUES ('S001','C101','A0'),('S001','C102','B+'),('S002','C101','B0'),('S003','C201','A+')) v(sn,cc,g) JOIN acad.student s ON s.stud_no=v.sn JOIN acad.course c ON c.course_cd=v.cc;
INSERT INTO acad.contact (stud_id, subject_cd, type_cd, emerg_yn) SELECT s.stud_id, v.sc, v.tc, v.e FROM (VALUES ('S001','SELF','MOBILE',false),('S001','MOTHER','MOBILE',true),('S001','SELF','ADDR',false)) v(sn,sc,tc,e) JOIN acad.student s ON s.stud_no=v.sn;
INSERT INTO acad.pi_contact SELECT c.contact_id, v.val, now(), now() FROM acad.contact c JOIN acad.student s ON s.stud_id=c.stud_id JOIN (VALUES ('SELF','MOBILE','010-9999-2222'),('MOTHER','MOBILE','010-7777-8888'),('SELF','ADDR','경기도 ○○시 ○○로')) v(sc,tc,val) ON v.sc=c.subject_cd AND v.tc=c.type_cd WHERE s.stud_no='S001';
SELECT 'rows: enrollment='||(SELECT count(*) FROM acad.enrollment)||' contact='||(SELECT count(*) FROM acad.contact)||' pi_contact='||(SELECT count(*) FROM acad.pi_contact);
-- 핵심 질문: S001 휴대전화 변경은 한 곳만 바뀌는가
UPDATE acad.pi_contact pc SET contact_val='010-1234-0000' FROM acad.contact c JOIN acad.student s ON s.stud_id=c.stud_id WHERE pc.contact_id=c.contact_id AND s.stud_no='S001' AND c.subject_cd='SELF' AND c.type_cd='MOBILE';
SELECT 'OK: S001 mobile updated rows='||count(*) FROM acad.pi_contact WHERE contact_val='010-1234-0000';
SAVEPOINT a; DO $$ BEGIN INSERT INTO acad.enrollment SELECT stud_id, course_id, 'A0' FROM acad.enrollment LIMIT 1; RAISE EXCEPTION 'FAIL: dup enrollment allowed'; EXCEPTION WHEN unique_violation THEN RAISE NOTICE 'OK: duplicate enrollment blocked'; END $$; ROLLBACK TO a;
SAVEPOINT b; DO $$ BEGIN UPDATE acad.enrollment SET grade_cd='Z' WHERE true; RAISE EXCEPTION 'FAIL: bad grade allowed'; EXCEPTION WHEN check_violation THEN RAISE NOTICE 'OK: invalid grade blocked'; END $$; ROLLBACK TO b;
SAVEPOINT c; DO $$ BEGIN DELETE FROM acad.department WHERE dept_cd='D01'; RAISE EXCEPTION 'FAIL: dept delete allowed'; EXCEPTION WHEN foreign_key_violation THEN RAISE NOTICE 'OK: department with students RESTRICTed'; END $$; ROLLBACK TO c;
DELETE FROM acad.contact c USING acad.student s WHERE s.stud_id=c.stud_id AND s.stud_no='S001' AND c.type_cd='ADDR';
SELECT 'OK: pi_contact cascaded, remaining='||count(*) FROM acad.pi_contact;
ROLLBACK;
