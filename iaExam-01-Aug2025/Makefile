# Makefile

# Clean target: delete all .tex files
cleanAll:
	rm -f *.tex
	rm -f *.out
	rm -f *.log
	rm -f *.aux
	rm -f *.pdf
	rm -f *.toc
	rm -f *.gz
	rm -f *.fls
	rm -f *.vrb
	rm -f *.nav
	rm -f *.snm	
clean:
	rm -f *.out
	rm -f *.log
	rm -f *.aux
	rm -f *.toc
	rm -f *.gz
	rm -f *.fls
	rm -f *.vrb
	rm -f *.nav
	rm -f *.snm
	
all:
	python3 00-createStudentList.py
	python3 01-scheduleTestInRooms.py
	python3 02a-allocateExaminationDuty.py
	python3 02b-onlyRegenerateExamDutyLatexReport.py
	pdflatex faculty_duties.tex
	pdflatex faculty_duties.tex
	python3 03-generateTestSchedule.py
	pdflatex schedule_sections.tex
	pdflatex schedule_sections.tex
	python3 04-studentSchedule.py
	pdflatex students_schedule.tex
	pdflatex students_schedule.tex
	python3 05-attendanceSheet.py
	pdflatex attendance_sheets.tex
	pdflatex attendance_sheets.tex