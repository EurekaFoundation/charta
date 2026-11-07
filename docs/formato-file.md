# Il formato file `.charta` (versione 1)

Un documento Charta è un archivio **ZIP** con questa struttura:

| Percorso | Contenuto |
|---|---|
| `mimetype` | Il testo `application/x-charta`. È il primo file e non è compresso, così il tipo si riconosce leggendo i primi byte. |
| `document.json` | Pagine, oggetti e proprietà, in UTF-8. |
| `assets/<id>.<ext>` | Le immagini originali, non ricompresse. `<id>` è l'inizio dell'hash SHA-1 del file. |
| `thumbnail.png` | Anteprima della prima pagina (facoltativa). |

## `document.json`

Tutte le misure sono in **millimetri**; l'origine è l'angolo in alto a
sinistra della pagina. I colori sono stringhe `#rrggbb` oppure `#aarrggbb`
(con trasparenza); `null` significa "nessun colore".

```json
{
  "version": 1,
  "title": "Volantino",
  "assets": { "3f2a9c01b7e4d5a6": "jpg" },
  "merge": { "source": "/percorso/iscritti.xlsx" },
  "pages": [
    {
      "width": 210, "height": 297,
      "margins": [12, 12, 12, 12],
      "background": "#ffffff",
      "guides": { "x": [105], "y": [40, 150] },
      "items": [ ... ]
    }
  ]
}
```

`margins` è nell'ordine alto, destra, basso, sinistra. `guides` contiene le guide
verticali (`x`) e orizzontali (`y`) della pagina. Gli oggetti in `items` sono
elencati dal più in basso al più in alto. `merge` (facoltativo) ricorda il file
dei dati della stampa unione.

### Proprietà comuni a tutti gli oggetti

| Campo | Significato |
|---|---|
| `type` | `text`, `image`, `shape` o `group` |
| `id` | identificativo unico dell'oggetto nel documento |
| `x`, `y` | posizione dell'angolo in alto a sinistra (prima della rotazione) |
| `w`, `h` | larghezza e altezza |
| `rotation` | rotazione in gradi, attorno al centro dell'oggetto |
| `opacity` | da 0 a 1 |
| `locked` | `true` se l'oggetto è bloccato |

### Testo (`text`)

| Campo | Significato |
|---|---|
| `html` | contenuto in HTML (sottoinsieme supportato da Qt) |
| `fill`, `stroke`, `stroke_width` | riempimento, colore e spessore del bordo (pt) |
| `padding` | spazio interno in mm |
| `valign` | `top`, `middle` o `bottom` |
| `next` | `id` della cornice in cui continua il testo (testo collegato), oppure `null` |
| `continues` | `true` se il testo di questa cornice prosegue l'ultimo paragrafo della precedente |

Le cornici collegate formano una catena (anche su pagine diverse). Ogni cornice
salva solo la propria parte di testo; unendo gli `html` nell'ordine della catena
si ottiene il testo completo. Le tabelle sono tabelle HTML dentro `html`. I campi
della stampa unione sono scritti nel testo come `{{NomeColonna}}`.

Le dimensioni dei caratteri sono in punti tipografici.

### Immagine (`image`)

| Campo | Significato |
|---|---|
| `asset` | id dell'immagine in `assets/`, oppure `null` per un segnaposto vuoto |
| `fit` | `fill` (riempie e ritaglia), `fit` (intera), `stretch` (deforma) |
| `stroke`, `stroke_width` | bordo |

### Forma (`shape`)

| Campo | Significato |
|---|---|
| `shape` | `rect`, `ellipse`, `line` (linea orizzontale a metà altezza, ruotabile) o `path` |
| `path` | solo per `path`: comandi `["M", x, y]`, `["L", x, y]`, `["Q", x1, y1, x, y]`, `["C", x1, y1, x2, y2, x, y]`, `["Z"]` con coordinate da 0 a 1 rispetto a `w` e `h` |
| `fill`, `stroke`, `stroke_width` | riempimento e bordo |
| `radius` | raggio degli angoli dei rettangoli, in mm |

### Gruppo (`group`)

| Campo | Significato |
|---|---|
| `items` | gli oggetti del gruppo, con `x` e `y` relativi all'angolo del gruppo |

## Compatibilità

Un programma che legge il formato deve ignorare i campi e i tipi di oggetto
che non conosce. I file delle versioni 0.1 e 0.2 di Charta si aprono senza
modifiche: i campi aggiunti dopo sono tutti facoltativi. Se `version` è maggiore di quella supportata, Charta rifiuta
di aprire il file invece di perdere dati in silenzio.
