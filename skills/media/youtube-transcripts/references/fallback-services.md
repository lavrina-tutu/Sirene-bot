# Fallback-сервисы транскрипта YouTube (сигнатуры отказов, проверено 10.2026)

Основной метод — `web_extract` на watch-URL (см. SKILL.md). Ниже — быстрые сигнатуры, чтобы не жечь время при повторе. Начинать с них нельзя — только после неудачи основного пути.

## Прямые API с ВМ
- yt-dlp / youtube_transcript_api: SSL_ERROR_ZERO_RETURN / UNEXPECTED_EOF — ретраи бесполезны.
- timedtext (captionTracks baseUrl + `&lang=en`, `&fmt=json3`, `&fmt=vtt`): HTTP 200, тело пустое.
- InnerTube `get_transcript` (params из getTranscriptEndpoint страницы): 400 FAILED_PRECONDITION — нужен POT-токен.

## Браузерный UI
- «…» More actions главного видео в гостевой сессии: только «Watch ad-free» + «Report»; «Show transcript» появляется только в авторизованной сессии (логина в vault нет — не лезть).
- Вкладки «Description/Comments» в новых макетах — не транскрипт.
- Кнопка More actions часто вне вьюпорта headless-браузера (клики по координатам бьют мимо); даже видимая кнопка меню не открывает пункт транскрипта для гостя.

## Сторонние веб-сервисы
- youtubetotranscript.com: POST/GET → Cloudflare challenge 403; в headless challenge не решается автоматически.
- notegpt.io/api/v2/video-transcript: POST → 405, GET → «login expired».
- tactiq-apps-prod.tactiq.io/transcript: 401 «Missing App Check token».
- api.kome.ai/api/tools/youtube_transcripts: 522/429.

## Invidious / Piped
- Список живых инстансов: `curl https://api.invidious.io/instances.json` — брать только `type=https` и `api:true`, проверять быстрым curl перед навигацией.
- Проверенные 10.2026: inv.nadeko.net (таймаут), yewtu.be и invidious.f5.si (Cloudflare), invidious.nerdvpn.de (ERR_HTTP2_PROTOCOL_ERROR), yt.chocolatemoo53.com (api:true, таймаут), invidious.privacyredirect.com (301).
- Piped (pipedapi.*): 502/500/301, не работает.

## Рабочий запасной источник
- `web_search` по `<спикер> <название> transcript`: поисковик индексирует полный ASR-текст; LinkedIn-посты авторов/компаний часто цитируют ключевые куски доклада — годится для перекрёстной проверки и коротких видео.
