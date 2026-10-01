# Navigation sample - expected results

This original three-page fixture exercises actual PDF links, not inferred printed references.

1. Source page 1 links to the section heading and note on page 2 and to the LeafPress website. The section and note should land at different reconstructed blocks.
2. Source page 2 has separate links back to the reference on page 1. These are ordinary hyperlinks, without inferred popup-note behavior.
3. Source page 3 is a preserved landscape image, followed by an available clickable website entry.
4. The contents menu nests "Linked section" under "Reading and navigation" and keeps "Preserved slide" at the top level.
5. Full conversion reports four internal links, two external links and zero skipped links. Converting only page 1 excludes its two cross-page targets, retains the website link and reports the omissions.
6. For manual regions, use the original `conversion-lab.pdf` page 2 and select part of its table. The expanded green bounds and exported image must contain all five rows and three columns; surrounding prose and TABLE_END_MARKER remain readable and adjustable.

The desktop comparison is approximate. Check jumps, returned reading positions, external-link handling and cropped image zoom on the actual Kindle.
