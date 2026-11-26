# Границы проверки при возврате: что сверять одним проходом

Когда серия возвратов исполнителя к архитектору объяснена дефектом архитектурной проработки («план предписал одно, код ведёт себя иначе»), перед следующей большой порцией исполнитель делает ОДНУ сквозную проверку всех оставшихся границ. Формат строки на каждый owner: `§/IAC/ID → actual owner/call chain → input → expected rc/deltas → observed trace → allowed fix / conflict / NOT_RUN`. Недостижимый node — `NOT_IMPLEMENTED`, не PASS.

## Границы и что в них сверять одновременно (чтобы не получить следующую поштучную эскалацию)

| Граница / существующие проверки | Что проверять одновременно |
|---|---|
| Resolver → static config → SDK (§12, H01/H04) | Concrete priority explicit/YAML/ENV, selector только status, exact wire model; отсутствие operands после prepare, до constructor/send. Отрицательные данные должны доходить до static branch. |
| SDK → worker → parent → classifier/result (§13, H02…H10) | Реальный установленный SDK с synthetic transport; malformed 2xx/shape/whitespace → exact local marker/rc=4, реальные status/transport/static/unknown worker → прежний rc=3. Проверить quoted fatal, stale success, zero publisher/result/receipt и recorder ErrorBus, single send/zero alternative. H02/H03 нельзя заменять тестами H05. |
| Split/coverage → publisher → metadata/result/complete (H06…H09, M01…10, O, W) | N=1/2/3/10 и сокращение N; старые parts/alias/hash/metadata, prepare identity и все faultpoint до/после записи. Последовательные replace + отдельная запись state: проверить сбой после уже заменённой части и остатки прежнего N. Единственный single-part fault не доказывает сохранность multipart. |
| MIG: T11 / D01…06 (§11) | Оба slot и accepts, прямой ORCH/done, early done no-op, reuse/missing/substituted proof. У отказа единственная причина — проверяемое предусловие. Непараметризованный happy path не заменяет вариации. |
| Handoff / legacy / refresh (B01…12, L01…08, §2.6/2.7/7) | Недоступный A, old references в неизменённых документах, проверенная local projection до G1, существующий producer refresh для produced extract. Никакого готового пути от fixture. |
| Bootstrap / rework / branch history (T/P/N/C/V) | Десять кейсов до последних ролей, absent/planned/present и собственные LIGHT IAC; обязательные inputs, resolved target, законные rework/set-case/recipe-add с сохранённой историей. Разные ID должны исполнять разные предписанные действия. |
| Выпуск (E/F и IAC-15…20) | Launcher должен выполнить все §7 traces, а не только вернуть rc=0/первый trace. Candidate/installed/source hashes и фактически loaded rules наблюдаемы. |

## Граница «сам / эскалация» для исполнителя

**Продолжает сам (без архитектора):** реализовать отсутствующие nodes и полный набор их actions/oracles/subcases в разрешённых tests/fixture; поправить типовые fixture, сохраняя прежние assertions; в разрешённых файлах довести уже описанные алгоритмы; исправить подтверждённый product-gap в уже разрешённом owner с прежним требуемым результатом; выполнить targeted tests и затем общий regression.

**Требует возврата до изменения:** удалить/ослабить assertion, подменить oracle, skip/xfail обязательного сценария, изменить ID/node/матрицу, принять неполную трассу; новый target/изменение read-only copied input/нового перехода/owner/формата proof/способа выбора нормы; изменить набор local/provider ошибок, marker/rc, resolver/send guard/classifier/таймаут/retry/fallback либо protected функцию за пределами разрешённых §; противоречие двух норм, исправление вне функциональной цели разрешённого файла, новая зависимость/ENV/config key.

Зелёный частный regression НЕ даёт исполнителю права менять семантику envelope/rc или расширять разрешённые функции — corpus может ещё не содержать нужного отрицательного пути.

## Проверка допущений на будущих плановых ревизиях

Если новая содержательная плановая ревизия действительно нужна, архитектор в начале заполняет таблицу границ для ВСЕЙ затронутой области (success, invalid result, provider failure, stale success, прямой entrypoint). Ревизор сверяет её против исходников/изолированной улики и ищет противоречие вида «требуем локальный отказ» + «все ошибки обязаны идти в provider-fatal». Зелёные регрессии исторических функций не доказывают пригодность reuse.
