# LeafPress 0.1 - Primo avvio

Il prototipo converte i PDF in EPUB sul tuo computer. Mantiene il testo adattabile quando possibile e conserva tabelle complesse, formule, diagrammi e slide tramite immagini ritagliate.

1. Estrai lo ZIP in una cartella normale, per esempio `Documenti\LeafPress`.
2. Se non lo hai, installa **Python 3.12 o 3.13** dal sito ufficiale, abilitando il launcher o l'opzione per aggiungerlo al PATH.
3. Esegui **`setup-windows.bat`** una volta. Serve Internet per scaricare le dipendenze.
4. Esegui **`start-windows.bat`**. Le conversioni successive sono locali e non richiedono un servizio online.
5. Apri **`examples\conversion-lab.pdf`**: contiene testo, tabelle, formule, diagrammi, colonne, una scansione simulata e una slide.
6. Seleziona pagina 2 e premi **Preview page** per confrontare la tabella.
7. Scegli la destinazione e premi **Create EPUB**.

Il pacchetto contiene il codice e gli script di avvio. Un `.exe` Windows precompilato non è incluso. `build-windows.bat` permette di creare una cartella applicazione su Windows; quel build richiede ancora una verifica sul sistema Windows.

## Impostazioni utili

| Opzione | Effetto |
| --- | --- |
| Hybrid | Testo adattabile; ritagli per gli elementi complessi |
| Preserve all pages | Ogni pagina resta un'immagine con l'aspetto del PDF |
| Tables / Auto | Tabelle semplici in HTML, casi complessi come immagini |
| Tables / Images | Tutte le tabelle rilevate vengono conservate come immagini |
| Compact | Immagini in grigio, risoluzione e dimensioni inferiori |
| Balanced | Impostazione iniziale consigliata per le immagini |
| Sharp | Ritagli a risoluzione maggiore |
| This page / Preserve appearance | Conserva visivamente solo la pagina selezionata |

La modalità Hybrid usa euristiche: controlla l'ordine del testo, le tabelle e le formule. Se una pagina non convince, applica **Preserve appearance** e genera di nuovo. La ricerca di tabelle senza bordi è sperimentale.

Le scansioni vengono conservate come immagini: **l'OCR non è ancora incluso**. Il testo nelle immagini non permette la selezione normale o il ridimensionamento indipendente. Le immagini di tabelle molto larghe richiedono comunque lo zoom sul Kindle.

L'anteprima desktop è approssimativa. Per verificare il risultato finale, invia l'EPUB tramite **Send to Kindle** e controllalo sul dispositivo. Puoi provare subito anche l'EPUB di esempio già incluso.

Accanto all'EPUB trovi un file `.report.json` con le scelte per pagina, le segnalazioni da controllare, i tempi e il picco di RAM del processo di conversione. Il file non include la RAM dell'interfaccia. La cartella `.preview` contiene gli elementi usati per il confronto e può essere rimossa dopo la verifica.

Con **Cancel** la conversione si ferma senza sostituire l'EPUB precedente. Un processo bloccato viene interrotto dall'interfaccia dopo cinque secondi. I limiti sulle immagini di uscita aiutano a contenere la memoria, ma non costituiscono un tetto rigido per qualsiasi PDF.

I dettagli tecnici, i test e i prossimi passi sono in `README.md` e `PROJECT_CONTEXT.md`.
