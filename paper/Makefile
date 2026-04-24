MAIN := main
PDFLATEX := pdflatex
BIBTEX := bibtex
PDFLATEX_FLAGS := -interaction=nonstopmode -halt-on-error

.PHONY: all clean distclean view arxiv

all: $(MAIN).pdf

# Use pdflatex + bibtex directly so we do not depend on latexmk being installed.
# Run pdflatex twice after bibtex so cross-references and citations settle.
$(MAIN).pdf: $(MAIN).tex references.bib sections/*.tex $(wildcard tables/*.tex) $(wildcard figures/*.pdf)
	$(PDFLATEX) $(PDFLATEX_FLAGS) $(MAIN)
	$(BIBTEX) $(MAIN) || true
	$(PDFLATEX) $(PDFLATEX_FLAGS) $(MAIN)
	$(PDFLATEX) $(PDFLATEX_FLAGS) $(MAIN)

clean:
	rm -f $(MAIN).aux $(MAIN).log $(MAIN).toc $(MAIN).out $(MAIN).bbl $(MAIN).blg \
	      $(MAIN).fls $(MAIN).fdb_latexmk $(MAIN).synctex.gz \
	      sections/*.aux

distclean: clean
	rm -f $(MAIN).pdf

view: all
	open $(MAIN).pdf

# Build the arXiv submission tarball. arXiv requires the compiled .bbl since
# they do not run BibTeX. Include the PDF figures, tables, and section files.
arxiv: all
	@rm -rf arxiv-build
	@mkdir -p arxiv-build
	@cp $(MAIN).tex references.bib arxiv-build/
	@cp $(MAIN).bbl arxiv-build/ 2>/dev/null || echo "No .bbl produced; run 'make' first."
	@cp -r sections figures tables arxiv-build/
	@tar -czf $(MAIN)-arxiv.tar.gz -C arxiv-build .
	@rm -rf arxiv-build
	@echo "Created $(MAIN)-arxiv.tar.gz"
