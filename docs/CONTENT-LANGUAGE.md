# Content language choice (Media centre)

Next to the genre the catalogue offers a second choice: the **language of the content** — `All languages ▾` at the
start of the genre row (in Video, which has no genres, it stands alone). It is offered for All, Films, Series, Video
and Music, and lasts while Safeer OS is open, like the genre. The interface language and English are at the top of
the list, the rest in alphabetical order, with names in the interface language.

The same choice exists in Safeer OS for Android (0.5.48), with the same rules and the same list of 38 languages
(`core/izvirni_jezik.py` here, `os/IzvirniJezik.kt` there, with the same test cases). The language variants
described below were added here first.

## Where the language comes from

| Source | Language |
| --- | --- |
| TMDB catalogue (shown when a player source is added) | original language of the title; the choice goes to `/discover` as `with_original_language` (film and series separately; for "All" both, interleaved) |
| PeerTube | stated by the video; the instance is already asked for the language (`languageOneOf`), the catalogue then selects exactly (the instance also returns videos that only have subtitles in it) |
| Jamendo | language of the lyrics (`lang`, `include=musicinfo`); instrumental tracks have none |
| Public-domain films, radio | stated by the entry |
| Titles from add-ons with an IMDb id | **Wikidata**: languages of the work (P364) and countries of origin (P495) |

A title can list several languages. The choice uses the **main** one (`izvirni_jezik.glavni`):

1. a language that is at home in one of the countries of origin wins (an American film with some French and
   Japanese dialogue is English);
2. between several such languages English wins;
3. without English all of them stay (a Belgian film in French and Dutch is found under both);
4. Serbo-Croatian films of former Yugoslavia are found under Croatian, Serbian and Bosnian.

Wikidata often records a **variant** of a language instead of the language itself: "American English" (Breaking
Bad), "Brazilian Portuguese", "Swiss German", "Quebec French", "Egyptian Arabic", "Putonghua". A variant belongs to
its language, and so do the dialects that catalogues keep under the language of the country (Neapolitan, Sicilian,
Bavarian, the Chinese languages) — as TMDB does. Without this such a title would count as a title of unknown
language and disappear while a language is selected. The table (`izvirni_jezik.JEZIKI`) holds every variant among
the 220 most frequent values of P364 (checked on 4 October 2026); what it does not cover are languages that are not
on the list of 38.

Catalogues keep some languages under their own codes (TMDB: `sh` Serbo-Croatian, `cn` Cantonese, `nb` Bokmål); the
choice covers them (`izvirni_jezik.SORODNE`).

An entry whose language is not known is **not shown** while a language is selected — choosing "Slovenian" must not
show films of unknown language. An empty catalogue then says that nothing was found *in the selected language*.

Not in this version: listing titles of a language from Wikidata itself (Android does this for its public
catalogue). On the computer a title is shown only when one of the user's sources has it.

## What leaves the computer

Only while a language is selected:

* to Wikidata: the public IMDb ids of titles in the catalogue on screen. Titles that come from a **private** add-on
  (or from an add-on not yet known to be public) are never asked about;
* to PeerTube instances and Jamendo: the selected language as a query parameter;
* to TMDB: the selected language as a query parameter.

Nothing about the user, the installed add-ons or what is being watched. Requests to Wikidata identify the app as
`SafeerOS/1.0 (https://safeer.si)`, as Wikidata asks.

## Limits and caching

* At most four requests to Wikidata at a time, 80 titles each; a "too many requests" answer is respected
  (`Retry-After`); after a failed request Wikidata is not asked again for a minute, so the catalogue never waits for
  it repeatedly.
* A known language is kept for 180 days, an unknown one for 7 days (`izvirni-jeziki.tsv` next to the settings, at
  most 20 000 titles).
* A catalogue view with a selected language is cached like any other view; without a choice the cache key is the
  same as before, so saved views stay valid.

## A source that does not answer

The catalogue does not wait for a public source that is down (`core/zakoniti_viri.py`):

* a PeerTube instance has 5 s for a list; once the first instance has answered with videos the others get 1.5 s
  more — later answers stay in the cache for the next view;
* a server that fails slowly (we waited at least 3 s) is skipped for 5 minutes and then asked again in the
  background; a fast failure (refused connection, HTTP error) does not exclude it.

Measured on 4 October 2026 with one built-in instance down: first Video view 10.3 s → 2.1 s, further views
(another language) 10 s → under 1 s.
