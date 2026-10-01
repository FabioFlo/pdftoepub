# PdfToEpub converter 0.2 - Primo avvio

Il prototipo converte i PDF in EPUB sul tuo computer. Mantiene il testo adattabile quando possibile e conserva tabelle complesse, formule, diagrammi e slide tramite immagini ritagliate.

1. Estrai lo ZIP in una cartella normale, per esempio `Documenti\PdfToEpubConverter`.
2. Se non lo hai, installa **Python 3.12 o 3.13** dal sito ufficiale, abilitando il launcher o l'opzione per aggiungerlo al PATH.
3. Esegui **`setup-windows.bat`** una volta. Serve Internet per scaricare le dipendenze.
4. Esegui **`start-windows.bat`**. Le conversioni successive sono locali e non richiedono un servizio online.
5. Apri **`examples\conversion-lab.pdf`**: contiene testo, tabelle, formule, diagrammi, colonne, una scansione simulata e una slide.
6. Seleziona pagina 2 e premi **Preview page** per confrontare la tabella.
7. Scegli la destinazione e premi **Create EPUB**.

Il repository contiene i sorgenti e gli script. `build-windows.bat` crea una cartella applicazione su Windows e verifica il processo di conversione compilato. GitHub Actions genera anche **PdfToEpubConverter-0.2.0-Windows-portable** dopo i test: scaricalo da una esecuzione riuscita nella pagina Actions, estrailo e apri `PdfToEpubConverter.exe`. Mantieni tutta la cartella insieme; include Python. Lo ZIP dei sorgenti non è un eseguibile. I controlli automatici non sostituiscono la prova pratica dell'interfaccia su Windows.

## Impostazioni utili

| Opzione | Effetto |
| --- | --- |
| Hybrid | Testo adattabile; ritagli per gli elementi complessi |
| All page images | Ogni pagina resta un'immagine con l'aspetto del PDF |
| Tables / Auto | Tabelle semplici in HTML, casi complessi come immagini |
| Tables / Images | Tutte le tabelle rilevate vengono conservate come immagini |
| Compact | Immagini in grigio, risoluzione e dimensioni inferiori |
| Balanced | Impostazione iniziale consigliata per le immagini |
| Sharp | Ritagli a risoluzione maggiore |
| This page / Preserve appearance | Conserva visivamente solo la pagina selezionata |
| Preserve PDF and web links | Conserva i link PDF alle pagine incluse e i link web/email |
| Select area to preserve | Trascina sul PDF per conservare una regione come immagine |
| Profile / Technical | Hybrid e Balanced, con le tabelle rilevate come immagini |
| Save profile... | Salva le preferenze generali con un nome |

La modalità Hybrid usa euristiche: controlla l'ordine del testo, le tabelle e le formule. Se una pagina non convince, applica **Preserve appearance** e genera di nuovo. La ricerca di tabelle senza bordi è sperimentale.

Con **Select area to preserve** puoi selezionare un'area del PDF. Il ritaglio si espande per includere interamente le righe, tabelle, formule e figure intersecate. Dopo l'anteprima il rettangolo verde mostra l'area effettiva. **Undo area** annulla l'ultima selezione; **Clear page areas** pulisce la pagina. Le selezioni si azzerano aprendo un altro PDF.

I link reali del PDF diventano collegamenti ai blocchi corrispondenti dell'EPUB; nelle immagini compare una voce cliccabile accanto al contenuto. Le note già collegate mantengono i link ordinari, senza popup ricostruiti. Un testo come "vedi pagina 12" non diventa automaticamente un link. Le destinazioni escluse sono omesse e segnalate. L'anteprima di una sola pagina esclude i link alle altre; l'esportazione completa conserva i collegamenti tra le pagine scelte.

Prova **examples\navigation-lab.pdf** e il relativo EPUB: indice gerarchico, riferimenti interni, note con ritorno, link web e una slide. I nuovi collegamenti v0.2 richiedono una prova sul Kindle; il risultato v0.1 è già stato verificato positivamente da Flo.

L'app ricorda preferenze, profili e ultime cartelle sul computer. Titolo, autore, intervalli e correzioni del documento non entrano nei profili generali. Il pannello impostazioni scorre nelle finestre piccole.

Le scansioni vengono conservate come immagini: **l'OCR non è ancora incluso**. Il testo nelle immagini non permette la selezione normale o il ridimensionamento indipendente. Le immagini di tabelle molto larghe richiedono comunque lo zoom sul Kindle.

L'anteprima desktop è approssimativa. Per verificare il risultato finale, invia l'EPUB tramite **Send to Kindle** e controllalo sul dispositivo. Puoi provare subito anche l'EPUB di esempio già incluso.

Accanto all'EPUB trovi un file `.report.json` con le scelte per pagina, le segnalazioni da controllare, i tempi e il picco di RAM del processo di conversione. Il file non include la RAM dell'interfaccia. La cartella `.preview` contiene gli elementi usati per il confronto e può essere rimossa dopo la verifica.

Con **Cancel** la conversione si ferma senza sostituire l'EPUB precedente. Un processo bloccato viene interrotto dall'interfaccia dopo cinque secondi. I limiti sulle immagini di uscita aiutano a contenere la memoria, ma non costituiscono un tetto rigido per qualsiasi PDF.

I dettagli tecnici, i test e i prossimi passi sono in `README.md` e `PROJECT_CONTEXT.md`.
