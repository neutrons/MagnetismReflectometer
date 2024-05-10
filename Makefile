prefix := /SNS/REF_M/shared

all:
	@echo "Run 'make install' to install the automated reduction code for MR"


install: autoreduce

base:
	cp -R src/mr_reduction/*.py $(prefix)/autoreduce/mr_reduction

autoreduce: base
	cp -R src/autoreduce/*.template $(prefix)/autoreduce
	cp -R src/livereduce/*.py $(prefix)/livereduce

test:
	python tests/unit_tests.py

check:
	diff --exclude="*.pyc" -r src/mr_reduction $(prefix)/autoreduce/mr_reduction
	diff --exclude="*.pyc" --exclude="livereduce.conf" -r -q src/livereduce $(prefix)/livereduce
	diff --exclude="*.pyc" -r -q src/autoreduce/*.template $(prefix)/autoreduce

.PHONY: install
.PHONY: base
.PHONY: autoreduce
.PHONY: test
.PHONY: check

