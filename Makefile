prefix := /SNS/REF_M/shared

all:
	@echo "Run 'make install' to install the automated reduction code for MR"


install: autoreduce

base:
	cp -R mr_reduction/*.py $(prefix)/autoreduce/mr_reduction

autoreduce: base
	cp -R autoreduce/*.template $(prefix)/autoreduce
	cp -R livereduce/*.py $(prefix)/livereduce

test:
	python test/unit_tests.py

check:
	diff --exclude="*.pyc" -r mr_reduction $(prefix)/autoreduce/mr_reduction
	diff --exclude="*.pyc" --exclude="livereduce.conf" -r -q livereduce $(prefix)/livereduce
	diff --exclude="*.pyc" -r -q autoreduce/*.template $(prefix)/autoreduce

.PHONY: install
.PHONY: base
.PHONY: autoreduce
.PHONY: test
.PHONY: check

