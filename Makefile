prefix := /SNS/REF_M/shared

all:
	@echo "Run 'make install' to install the automated reduction code for MR"


install: autoreduce

base:
	cp -R mr_reduction/*.py $(prefix)/autoreduce/mr_reduction

autoreduce: base
	cp -R autoreduce/*.template $(prefix)/autoreduce
	cp -R livereduce/*.py $(prefix)/livereduce

.PHONY: install
.PHONY: base
.PHONY: autoreduce

