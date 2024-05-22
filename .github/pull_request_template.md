# Description of the changes

# Manual test for the reviewer
<!-- Instructions for testing here. -->

# Check list for the reviewer
- [ ] best software practices
    + [ ] clearly named variables (better to be verbose in variable names)
    + [ ] code comments explaining the intent of code blocks
- [ ] All the tests are passing
- [ ] The documentation is up to date
- [ ] code comments added when explaining intent

### Execution of tests requiring the /SNS and /HFIR filesystems
It is strongly encouraged that the reviewer runs the following tests in their local machine
because these tests are not run by the GitLab CI. It is assumed that the reviewer has the /SNS and /HFIR filesystems
remotely mounted in their machine.

```bash
cd /path/to/my/local/mr_reduction/repo/
git fetch origin merge-requests/<MERGE_REQUEST_NUMBER>/head:mr<MERGE_REQUEST_NUMBER>
git switch mr<MERGE_REQUEST_NUMBER>
conda activate <my_mr_reduction_environment>
pytest -m mount_eqsans ./tests/unit/ ./tests/integration/
```
In the above code snippet, substitute `<MERGE_REQUEST_NUMBER>` for the actual merge request number. Also substitute
`<my_mr_reduction_environment>` with the name of the conda environment you use for development. It is critical that
you have installed the repo in editable mode with `pip install -e .` or `conda develop .`

# Check list for the author
- [ ] I have added tests for my changes
- [ ] I have updated the documentation accordingly
- [ ] I ran the tests requiring the /SNS and /HFIR filesystems
- [ ] I'm including a link to IBM EWM Story or Defect

# Check list for the pull request
- [ ] source refactored/incremented
- [ ] tests for my changes
- [ ] updated the documentation accordingly

# References
<!-- Links to related issues or pull requests -->
<!-- Links to IBM EWM items if aaplicable -->
