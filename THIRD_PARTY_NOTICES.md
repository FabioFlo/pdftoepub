# Dependencies and licensing

LeafPress source is provided under GNU AGPL v3 or later. The complete license is in `LICENSE`. Copyright (c) 2026 LeafPress contributors.

Dependencies are downloaded during setup; third-party binaries are not embedded in this source ZIP.

| Component | Use | Upstream licensing information |
| --- | --- | --- |
| PyMuPDF / MuPDF | PDF parsing and rendering | GNU AGPL or commercial licensing from Artifex: https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright |
| PySide6 Essentials / Shiboken6 / Qt | Desktop interface | LGPLv3 / GPLv3 / commercial options, with component-specific notices: https://doc.qt.io/qtforpython-6/ |
| Python | Runtime | Python Software Foundation License: https://docs.python.org/3/license.html |
| ReportLab | Optional original fixture generation | BSD license: https://github.com/MrBitBucket/reportlab-mirror/blob/master/LICENSE.txt |
| Pillow | Optional original fixture generation | HPND / component notices: https://github.com/python-pillow/Pillow/blob/main/LICENSE |
| PyInstaller | Optional native build | GPL with an exception for generated bundles: https://pyinstaller.org/en/stable/license.html |

The original sample PDF, sample EPUB, and test fixture source are part of this project. Real study PDFs used during verification are not redistributed here. An executable distribution must retain applicable third-party license files and notices along with the application.
