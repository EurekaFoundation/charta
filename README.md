# Charta

**Impaginazione libera e gratuita per volantini, locandine, brochure, giornalini,
menù e attestati.** Un'alternativa open source a Microsoft Publisher, pensata per
scuole, comuni, associazioni e piccole attività.

Microsoft ha ritirato Publisher nell'ottobre 2026. Charta offre uno strumento
semplice, che funziona offline, non richiede abbonamenti, salva in un formato
aperto e **apre i vecchi file `.pub`**.

Fa parte di **[Eureka Suite](https://github.com/EurekaFoundation)**: tema e lingua sono condivisi con gli altri programmi della suite tramite [eureka-core](https://github.com/EurekaFoundation/eureka-core).

*English: Charta is a free desktop publishing app (an open source alternative to
Microsoft Publisher). The interface is available in Italian and English.*

## Cosa sa fare (versione 0.3)

**Impaginazione**
- Pagine A3, A4, A5, A6, Lettera, biglietto da visita, cartolina o personalizzate,
  verticali o orizzontali, con margini e colore di sfondo; più pagine per documento.
- **Righelli** in millimetri e **guide**: si trascinano dal righello sulla pagina e
  si tolgono trascinandole di nuovo sul righello.
- **Calamita**: gli oggetti si agganciano a margini, guide, centro pagina e agli
  altri oggetti, con linee di riferimento. Griglia facoltativa.
- Allinea, distribuisci, ordine di sovrapposizione, rotazione, opacità, blocco.
- **Gruppi**: più oggetti si spostano, ridimensionano e ruotano insieme.

**Testo**
- Cornici di testo con caratteri, dimensioni, stili, colori, allineamenti,
  interlinea e allineamento verticale.
- **Testo che scorre tra cornici collegate**, anche su pagine diverse, come le
  caselle collegate di Publisher: si scrive in qualunque cornice e il testo passa
  da sé alla successiva. Ideale per giornalini e brochure su più colonne.
- **Tabelle** dentro le cornici: righe e colonne, intestazione, unione e divisione
  delle celle, colori delle celle, bordi.

**Immagini e forme**
- Immagini a piena risoluzione, con ritaglio o adattamento; si inseriscono anche
  trascinandole dal computer o incollandole.
- Rettangoli (anche arrotondati), ellissi, linee e forme libere.

**Stampa unione**
- Campi nel testo tra doppie graffe, per esempio `{{Nome}}`, collegati a un file
  **CSV o Excel**: attestati, badge, inviti e cartellini personalizzati in un clic.
- Anteprima riga per riga; esportazione in un unico PDF oppure in un PDF per ogni
  riga, con il nome del file preso da una colonna.

**Esportazione e stampa**
- PDF con testo vettoriale selezionabile; per la tipografia **abbondanza, segni di
  taglio** e **colori CMYK** (con Ghostscript).
- PNG/JPG fino a 300 dpi e stampa.

**Importazione**
- **File Microsoft Publisher (`.pub`)**, convertiti con LibreOffice in oggetti
  Charta modificabili: testi formattati, forme, linee, immagini, rotazioni e colori.
- Disegni LibreOffice Draw (`.odg`, `.fodg`).

**Interfaccia**: italiano e inglese (Visualizza → Lingua); la lingua predefinita
segue quella del sistema. Modelli pronti: volantino, locandina, menù, biglietto da
visita, attestato, brochure a tre ante.

## Installarlo

Scarica l'installatore dalla pagina
[Releases](https://github.com/EurekaFoundation/charta/releases):

| Sistema | File | Come si installa |
|---|---|---|
| Windows | `Charta-…-windows-setup.exe` | doppio clic e segui le istruzioni; non servono diritti di amministratore |
| Windows (senza installazione) | `Charta-…-windows-portable.zip` | estrai e avvia `Charta.exe` |
| macOS | `Charta-…-macos.dmg` | apri e trascina Charta in Applicazioni; la prima volta clic destro → Apri |
| Debian, Ubuntu, Mint | `Charta-…-linux-amd64.deb` | doppio clic, oppure `sudo apt install ./Charta-…-linux-amd64.deb` |
| Altre distribuzioni Linux | `Charta-…-linux-amd64.tar.gz` | estrai e avvia `Charta/Charta` |

L'installatore aggiunge Charta al menu e fa aprire i file `.charta` con un doppio
clic. Windows può mostrare l'avviso "PC protetto" perché il programma non è firmato
digitalmente: clic su "Ulteriori informazioni" → "Esegui comunque".

## Avviarlo dal codice sorgente

Serve Python 3.10 o successivo.

```bash
pip install -r requirements.txt
python -m charta
```

Per aprire direttamente un file: `python -m charta documento.charta` (funziona
anche con un `.pub` o un `.odg`).

Programmi facoltativi, gratuiti:

| Per | Serve |
|---|---|
| Aprire i file di Publisher | [LibreOffice](https://www.libreoffice.org) |
| PDF in CMYK | [Ghostscript](https://ghostscript.com) |

Charta li trova da sé se sono installati; se mancano, spiega cosa installare.

Gli installatori vengono creati da GitHub Actions a ogni nuova versione (tag `v*`):
vedi `.github/workflows/build.yml` e la cartella `packaging/`.

## Scorciatoie principali

| Tasto | Azione |
|---|---|
| V, T, I, B, R, E, L | Seleziona, Testo, Immagine, Tabella, Rettangolo, Ellisse, Linea |
| Doppio clic | Modifica il testo / scegli l'immagine |
| Frecce | Sposta di 1 mm (Maiusc 10 mm, Alt 0,1 mm) |
| Maiusc + maniglia | Ridimensiona mantenendo le proporzioni |
| Ctrl + rotellina | Zoom |
| Ctrl+D | Duplica |
| Ctrl+G / Ctrl+Maiusc+G | Raggruppa / separa |
| Ctrl+L | Blocca / sblocca |
| Ctrl+R | Righelli |
| Ctrl+M | Stampa unione |
| Ctrl+E | Esporta in PDF |

## Il formato .charta

È un archivio ZIP con un file `document.json` leggibile e le immagini originali,
documentato in [docs/formato-file.md](docs/formato-file.md): chiunque può leggerlo
o convertirlo anche senza Charta.

## Struttura del codice

```
charta/
├── app.py          avvio
├── units.py        millimetri ↔ punti, formati pagina
├── fonts.py        font predefiniti per ogni sistema operativo
├── merge.py        stampa unione (CSV/Excel, campi, esportazione)
├── document/       modello del documento e formato .charta
├── items/          oggetti: testo, immagine, forme, gruppi, tabelle,
│                   scorrimento del testo tra cornici (flow.py)
├── canvas/         pagina (scena), guide, calamita, vista, righelli
├── export/         PDF (anche CMYK), immagini, stampa
├── importers/      Publisher (.pub) e LibreOffice Draw (.odg)
├── templates/      modelli pronti
├── i18n/           traduzioni (en.py)
└── ui/             finestra, pannelli, dialoghi, icone
```

## Tradurre Charta in un'altra lingua

I testi dell'interfaccia sono scritti in italiano dentro `tr("...")`. Per una nuova
lingua basta copiare `charta/i18n/en.py` (per esempio in `fr.py`), tradurre i
valori e aggiungere la lingua a `LANGUAGES` e alla funzione `_load` in
`charta/i18n/__init__.py`.

## Test

```bash
pip install pytest
QT_QPA_PLATFORM=offscreen python -m pytest tests
```

I test di importazione da Publisher e di esportazione CMYK partono solo se
LibreOffice e Ghostscript sono installati. Per provare un vero file `.pub`:
`CHARTA_TEST_PUB=/percorso/file.pub python -m pytest tests -k publisher`.

## Licenza

Charta è software libero: puoi usarlo, studiarlo, modificarlo e ridistribuirlo
secondo i termini della **GNU General Public License versione 3** o successiva.
Vedi il file [LICENSE](LICENSE).

Un progetto [EurekaFoundation](https://github.com/EurekaFoundation).
