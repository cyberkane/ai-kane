# 🗺️ Архитектурная карта проекта MarmAI Gateway

**Последнее обновление:** 14.09.2026 22:39:28,34

## 📂 Структура каталогов и файлов

```text
    ├── .env
    ├── config.ini
    ├── main.py
    ├── project_architecture.md
    ├── pytest.ini
    ├── simple_function.py
    ├── .github/
        ├── workflows/
    ├── .vscode/
    ├── authorization/
        ├── authorization.py
    ├── database/
        ├── agent_graph.py
        ├── analytics.py
        ├── influx_storage.py
        ├── memory.py
        ├── storage.py
        ├── vault_storage.py
        ├── vector_storage.py
    ├── functions/
        ├── agent.py
        ├── autocomplete.py
        ├── chat.py
        ├── commit_track.py
        ├── embedder.py
        ├── health.py
    ├── instructions/
        ├── agent_pipeline.md
        ├── architecture.md
        ├── database_structure.md
        ├── system_prompt.md
    ├── metrics/
        ├── telemetry.py
    ├── tests/
        ├── conftest.py
        ├── test_chat.py
        ├── test_commit_track.py
        ├── test_infrastructure.py
        ├── test_sample_logic.py
        ├── test_simple_function.py
    ├── tools/
        ├── autotests.py
        ├── ide_events.py
        ├── infra_status.py
        ├── project_mapper.py
        ├── registry.py
        ├── system_time.py
        ├── test_runner.py
    ├── venv/
        ├── Include/
        ├── Lib/
            ├── site-packages/
                ├── pip/
                    ├── __init__.py
                    ├── __main__.py
                    ├── __pip-runner__.py
                    ├── _internal/
                        ├── build_env.py
                        ├── cache.py
                        ├── configuration.py
                        ├── exceptions.py
                        ├── main.py
                        ├── pyproject.py
                        ├── self_outdated_check.py
                        ├── wheel_builder.py
                        ├── __init__.py
                        ├── cli/
                            ├── autocompletion.py
                            ├── base_command.py
                            ├── cmdoptions.py
                            ├── command_context.py
                            ├── index_command.py
                            ├── main.py
                            ├── main_parser.py
                            ├── parser.py
                            ├── progress_bars.py
                            ├── req_command.py
                            ├── spinners.py
                            ├── status_codes.py
                            ├── __init__.py
                        ├── commands/
                            ├── cache.py
                            ├── check.py
                            ├── completion.py
                            ├── configuration.py
                            ├── debug.py
                            ├── download.py
                            ├── freeze.py
                            ├── hash.py
                            ├── help.py
                            ├── index.py
                            ├── inspect.py
                            ├── install.py
                            ├── list.py
                            ├── search.py
                            ├── show.py
                            ├── uninstall.py
                            ├── wheel.py
                            ├── __init__.py
                        ├── distributions/
                            ├── base.py
                            ├── installed.py
                            ├── sdist.py
                            ├── wheel.py
                            ├── __init__.py
                        ├── index/
                            ├── collector.py
                            ├── package_finder.py
                            ├── sources.py
                            ├── __init__.py
                        ├── locations/
                            ├── base.py
                            ├── _distutils.py
                            ├── _sysconfig.py
                            ├── __init__.py
                        ├── metadata/
                            ├── base.py
                            ├── pkg_resources.py
                            ├── _json.py
                            ├── __init__.py
                            ├── importlib/
                                ├── _compat.py
                                ├── _dists.py
                                ├── _envs.py
                                ├── __init__.py
                        ├── models/
                            ├── candidate.py
                            ├── direct_url.py
                            ├── format_control.py
                            ├── index.py
                            ├── installation_report.py
                            ├── link.py
                            ├── scheme.py
                            ├── search_scope.py
                            ├── selection_prefs.py
                            ├── target_python.py
                            ├── wheel.py
                            ├── __init__.py
                        ├── network/
                            ├── auth.py
                            ├── cache.py
                            ├── download.py
                            ├── lazy_wheel.py
                            ├── session.py
                            ├── utils.py
                            ├── xmlrpc.py
                            ├── __init__.py
                        ├── operations/
                            ├── check.py
                            ├── freeze.py
                            ├── prepare.py
                            ├── __init__.py
                            ├── build/
                                ├── build_tracker.py
                                ├── metadata.py
                                ├── metadata_editable.py
                                ├── metadata_legacy.py
                                ├── wheel.py
                                ├── wheel_editable.py
                                ├── wheel_legacy.py
                                ├── __init__.py
                            ├── install/
                                ├── editable_legacy.py
                                ├── wheel.py
                                ├── __init__.py
                        ├── req/
                            ├── constructors.py
                            ├── req_file.py
                            ├── req_install.py
                            ├── req_set.py
                            ├── req_uninstall.py
                            ├── __init__.py
                        ├── resolution/
                            ├── base.py
                            ├── __init__.py
                            ├── legacy/
                                ├── resolver.py
                                ├── __init__.py
                            ├── resolvelib/
                                ├── base.py
                                ├── candidates.py
                                ├── factory.py
                                ├── found_candidates.py
                                ├── provider.py
                                ├── reporter.py
                                ├── requirements.py
                                ├── resolver.py
                                ├── __init__.py
                        ├── utils/
                            ├── appdirs.py
                            ├── compat.py
                            ├── compatibility_tags.py
                            ├── datetime.py
                            ├── deprecation.py
                            ├── direct_url_helpers.py
                            ├── egg_link.py
                            ├── encoding.py
                            ├── entrypoints.py
                            ├── filesystem.py
                            ├── filetypes.py
                            ├── glibc.py
                            ├── hashes.py
                            ├── logging.py
                            ├── misc.py
                            ├── packaging.py
                            ├── retry.py
                            ├── setuptools_build.py
                            ├── subprocess.py
                            ├── temp_dir.py
                            ├── unpacking.py
                            ├── urls.py
                            ├── virtualenv.py
                            ├── wheel.py
                            ├── _jaraco_text.py
                            ├── _log.py
                            ├── __init__.py
                        ├── vcs/
                            ├── bazaar.py
                            ├── git.py
                            ├── mercurial.py
                            ├── subversion.py
                            ├── versioncontrol.py
                            ├── __init__.py
                    ├── _vendor/
                        ├── typing_extensions.py
                        ├── __init__.py
                        ├── cachecontrol/
                            ├── adapter.py
                            ├── cache.py
                            ├── controller.py
                            ├── filewrapper.py
                            ├── heuristics.py
                            ├── serialize.py
                            ├── wrapper.py
                            ├── _cmd.py
                            ├── __init__.py
                            ├── caches/
                                ├── file_cache.py
                                ├── redis_cache.py
                                ├── __init__.py
                        ├── certifi/
                            ├── core.py
                            ├── __init__.py
                            ├── __main__.py
                        ├── distlib/
                            ├── compat.py
                            ├── database.py
                            ├── index.py
                            ├── locators.py
                            ├── manifest.py
                            ├── markers.py
                            ├── metadata.py
                            ├── resources.py
                            ├── scripts.py
                            ├── util.py
                            ├── version.py
                            ├── wheel.py
                            ├── __init__.py
                        ├── distro/
                            ├── distro.py
                            ├── __init__.py
                            ├── __main__.py
                        ├── idna/
                            ├── codec.py
                            ├── compat.py
                            ├── core.py
                            ├── idnadata.py
                            ├── intranges.py
                            ├── package_data.py
                            ├── uts46data.py
                            ├── __init__.py
                        ├── msgpack/
                            ├── exceptions.py
                            ├── ext.py
                            ├── fallback.py
                            ├── __init__.py
                        ├── packaging/
                            ├── markers.py
                            ├── metadata.py
                            ├── requirements.py
                            ├── specifiers.py
                            ├── tags.py
                            ├── utils.py
                            ├── version.py
                            ├── _elffile.py
                            ├── _manylinux.py
                            ├── _musllinux.py
                            ├── _parser.py
                            ├── _structures.py
                            ├── _tokenizer.py
                            ├── __init__.py
                        ├── pkg_resources/
                            ├── __init__.py
                        ├── platformdirs/
                            ├── android.py
                            ├── api.py
                            ├── macos.py
                            ├── unix.py
                            ├── version.py
                            ├── windows.py
                            ├── __init__.py
                            ├── __main__.py
                        ├── pygments/
                            ├── cmdline.py
                            ├── console.py
                            ├── filter.py
                            ├── formatter.py
                            ├── lexer.py
                            ├── modeline.py
                            ├── plugin.py
                            ├── regexopt.py
                            ├── scanner.py
                            ├── sphinxext.py
                            ├── style.py
                            ├── token.py
                            ├── unistring.py
                            ├── util.py
                            ├── __init__.py
                            ├── __main__.py
                            ├── filters/
                                ├── __init__.py
                            ├── formatters/
                                ├── bbcode.py
                                ├── groff.py
                                ├── html.py
                                ├── img.py
                                ├── irc.py
                                ├── latex.py
                                ├── other.py
                                ├── pangomarkup.py
                                ├── rtf.py
                                ├── svg.py
                                ├── terminal.py
                                ├── terminal256.py
                                ├── _mapping.py
                                ├── __init__.py
                            ├── lexers/
                                ├── python.py
                                ├── _mapping.py
                                ├── __init__.py
                            ├── styles/
                                ├── _mapping.py
                                ├── __init__.py
                        ├── pyproject_hooks/
                            ├── _compat.py
                            ├── _impl.py
                            ├── __init__.py
                            ├── _in_process/
                                ├── _in_process.py
                                ├── __init__.py
                        ├── requests/
                            ├── adapters.py
                            ├── api.py
                            ├── auth.py
                            ├── certs.py
                            ├── compat.py
                            ├── cookies.py
                            ├── exceptions.py
                            ├── help.py
                            ├── hooks.py
                            ├── models.py
                            ├── packages.py
                            ├── sessions.py
                            ├── status_codes.py
                            ├── structures.py
                            ├── utils.py
                            ├── _internal_utils.py
                            ├── __init__.py
                            ├── __version__.py
                        ├── resolvelib/
                            ├── providers.py
                            ├── reporters.py
                            ├── resolvers.py
                            ├── structs.py
                            ├── __init__.py
                            ├── compat/
                                ├── collections_abc.py
                                ├── __init__.py
                        ├── rich/
                            ├── abc.py
                            ├── align.py
                            ├── ansi.py
                            ├── bar.py
                            ├── box.py
                            ├── cells.py
                            ├── color.py
                            ├── color_triplet.py
                            ├── columns.py
                            ├── console.py
                            ├── constrain.py
                            ├── containers.py
                            ├── control.py
                            ├── default_styles.py
                            ├── diagnose.py
                            ├── emoji.py
                            ├── errors.py
                            ├── filesize.py
                            ├── file_proxy.py
                            ├── highlighter.py
                            ├── json.py
                            ├── jupyter.py
                            ├── layout.py
                            ├── live.py
                            ├── live_render.py
                            ├── logging.py
                            ├── markup.py
                            ├── measure.py
                            ├── padding.py
                            ├── pager.py
                            ├── palette.py
                            ├── panel.py
                            ├── pretty.py
                            ├── progress.py
                            ├── progress_bar.py
                            ├── prompt.py
                            ├── protocol.py
                            ├── region.py
                            ├── repr.py
                            ├── rule.py
                            ├── scope.py
                            ├── screen.py
                            ├── segment.py
                            ├── spinner.py
                            ├── status.py
                            ├── style.py
                            ├── styled.py
                            ├── syntax.py
                            ├── table.py
                            ├── terminal_theme.py
                            ├── text.py
                            ├── theme.py
                            ├── themes.py
                            ├── traceback.py
                            ├── tree.py
                            ├── _cell_widths.py
                            ├── _emoji_codes.py
                            ├── _emoji_replace.py
                            ├── _export_format.py
                            ├── _extension.py
                            ├── _fileno.py
                            ├── _inspect.py
                            ├── _log_render.py
                            ├── _loop.py
                            ├── _null_file.py
                            ├── _palettes.py
                            ├── _pick.py
                            ├── _ratio.py
                            ├── _spinners.py
                            ├── _stack.py
                            ├── _timer.py
                            ├── _win32_console.py
                            ├── _windows.py
                            ├── _windows_renderer.py
                            ├── _wrap.py
                            ├── __init__.py
                            ├── __main__.py
                        ├── tomli/
                            ├── _parser.py
                            ├── _re.py
                            ├── _types.py
                            ├── __init__.py
                        ├── truststore/
                            ├── _api.py
                            ├── _macos.py
                            ├── _openssl.py
                            ├── _ssl_constants.py
                            ├── _windows.py
                            ├── __init__.py
                        ├── urllib3/
                            ├── connection.py
                            ├── connectionpool.py
                            ├── exceptions.py
                            ├── fields.py
                            ├── filepost.py
                            ├── poolmanager.py
                            ├── request.py
                            ├── response.py
                            ├── _collections.py
                            ├── _version.py
                            ├── __init__.py
                            ├── contrib/
                                ├── appengine.py
                                ├── ntlmpool.py
                                ├── pyopenssl.py
                                ├── securetransport.py
                                ├── socks.py
                                ├── _appengine_environ.py
                                ├── __init__.py
                                ├── _securetransport/
                                    ├── bindings.py
                                    ├── low_level.py
                                    ├── __init__.py
                            ├── packages/
                                ├── six.py
                                ├── __init__.py
                                ├── backports/
                                    ├── makefile.py
                                    ├── weakref_finalize.py
                                    ├── __init__.py
                            ├── util/
                                ├── connection.py
                                ├── proxy.py
                                ├── queue.py
                                ├── request.py
                                ├── response.py
                                ├── retry.py
                                ├── ssltransport.py
                                ├── ssl_.py
                                ├── ssl_match_hostname.py
                                ├── timeout.py
                                ├── url.py
                                ├── wait.py
                                ├── __init__.py
                ├── pip-24.2.dist-info/
        ├── Scripts/
```

## 🔬 Анализ ключевых модулей и зависимостей

### 📄 `main.py`
**Связанные компоненты:**
- 🔗 `functions.commit_track`
- 🔗 `metrics.telemetry`
- 🔗 `database.storage`
- 🔗 `functions.agent`
- 🔗 `functions.embedder`
- 🔗 `database.vector_storage`
- 🔗 `database.influx_storage`
- 🔗 `tools.test_runner`
- 🔗 `functions.chat`
- 🔗 `database.vault_storage`
- 🔗 `tools.infra_status`
- 🔗 `functions.autocomplete`
- 🔗 `functions.health`

### 📄 `database\agent_graph.py`
**Связанные компоненты:**
- 🔗 `langchain_core.tools`
- 🔗 `tools.registry`
- 🔗 `metrics.telemetry`

### 📄 `database\analytics.py`
**Связанные компоненты:**
- 🔗 `metrics.telemetry`

### 📄 `database\memory.py`
**Связанные компоненты:**
- 🔗 `metrics.telemetry`

### 📄 `database\vault_storage.py`
**Связанные компоненты:**
- 🔗 `metrics.telemetry`

### 📄 `database\vector_storage.py`
**Связанные компоненты:**
- 🔗 `metrics.telemetry`

### 📄 `functions\agent.py`
**Связанные компоненты:**
- 🔗 `tools.registry`

### 📄 `functions\autocomplete.py`
**Связанные компоненты:**
- 🔗 `metrics.telemetry`

### 📄 `functions\chat.py`
**Связанные компоненты:**
- 🔗 `metrics.telemetry`
- 🔗 `database.storage`
- 🔗 `database.vector_storage`
- 🔗 `database.influx_storage`
- 🔗 `tools.registry`

### 📄 `functions\commit_track.py`
**Связанные компоненты:**
- 🔗 `database.vector_storage`
- 🔗 `metrics.telemetry`

### 📄 `functions\embedder.py`
**Связанные компоненты:**
- 🔗 `metrics.telemetry`

### 📄 `functions\health.py`
**Связанные компоненты:**
- 🔗 `metrics.telemetry`

### 📄 `tools\autotests.py`
**Связанные компоненты:**
- 🔗 `metrics.telemetry`

### 📄 `tools\infra_status.py`
**Связанные компоненты:**
- 🔗 `metrics.telemetry`

### 📄 `tools\registry.py`
**Связанные компоненты:**
- 🔗 `tools.autotests`
- 🔗 `tools.test_runner`
- 🔗 `tools.infra_status`
- 🔗 `tools.system_time`
- 🔗 `tools.project_mapper`

### 📄 `tools\test_runner.py`
**Связанные компоненты:**
- 🔗 `metrics.telemetry`

### 📄 `venv\Lib\site-packages\pip\_internal\exceptions.py`
**Связанные компоненты:**
- 🔗 `itertools`

### 📄 `venv\Lib\site-packages\pip\_internal\self_outdated_check.py`
**Связанные компоненты:**
- 🔗 `functools`

### 📄 `venv\Lib\site-packages\pip\_internal\wheel_builder.py`
**Связанные компоненты:**
- 🔗 `pip._internal.utils.setuptools_build`

### 📄 `venv\Lib\site-packages\pip\_internal\cli\autocompletion.py`
**Связанные компоненты:**
- 🔗 `itertools`

### 📄 `venv\Lib\site-packages\pip\_internal\cli\cmdoptions.py`
**Связанные компоненты:**
- 🔗 `functools`

### 📄 `venv\Lib\site-packages\pip\_internal\cli\progress_bars.py`
**Связанные компоненты:**
- 🔗 `functools`

### 📄 `venv\Lib\site-packages\pip\_internal\cli\req_command.py`
**Связанные компоненты:**
- 🔗 `functools`

### 📄 `venv\Lib\site-packages\pip\_internal\cli\spinners.py`
**Связанные компоненты:**
- 🔗 `itertools`

### 📄 `venv\Lib\site-packages\pip\_internal\index\collector.py`
**Связанные компоненты:**
- 🔗 `itertools`
- 🔗 `functools`

### 📄 `venv\Lib\site-packages\pip\_internal\index\package_finder.py`
**Связанные компоненты:**
- 🔗 `itertools`
- 🔗 `functools`

### 📄 `venv\Lib\site-packages\pip\_internal\locations\base.py`
**Связанные компоненты:**
- 🔗 `functools`

### 📄 `venv\Lib\site-packages\pip\_internal\locations\__init__.py`
**Связанные компоненты:**
- 🔗 `functools`

### 📄 `venv\Lib\site-packages\pip\_internal\metadata\base.py`
**Связанные компоненты:**
- 🔗 `functools`

### 📄 `venv\Lib\site-packages\pip\_internal\metadata\__init__.py`
**Связанные компоненты:**
- 🔗 `functools`

### 📄 `venv\Lib\site-packages\pip\_internal\metadata\importlib\_envs.py`
**Связанные компоненты:**
- 🔗 `functools`

### 📄 `venv\Lib\site-packages\pip\_internal\models\link.py`
**Связанные компоненты:**
- 🔗 `itertools`
- 🔗 `functools`

### 📄 `venv\Lib\site-packages\pip\_internal\models\search_scope.py`
**Связанные компоненты:**
- 🔗 `itertools`

### 📄 `venv\Lib\site-packages\pip\_internal\network\auth.py`
**Связанные компоненты:**
- 🔗 `functools`

### 📄 `venv\Lib\site-packages\pip\_internal\network\session.py`
**Связанные компоненты:**
- 🔗 `functools`

### 📄 `venv\Lib\site-packages\pip\_internal\operations\check.py`
**Связанные компоненты:**
- 🔗 `functools`

### 📄 `venv\Lib\site-packages\pip\_internal\operations\build\metadata_legacy.py`
**Связанные компоненты:**
- 🔗 `pip._internal.utils.setuptools_build`

### 📄 `venv\Lib\site-packages\pip\_internal\operations\build\wheel_legacy.py`
**Связанные компоненты:**
- 🔗 `pip._internal.utils.setuptools_build`

### 📄 `venv\Lib\site-packages\pip\_internal\operations\install\editable_legacy.py`
**Связанные компоненты:**
- 🔗 `pip._internal.utils.setuptools_build`

### 📄 `venv\Lib\site-packages\pip\_internal\operations\install\wheel.py`
**Связанные компоненты:**
- 🔗 `itertools`

### 📄 `venv\Lib\site-packages\pip\_internal\req\req_install.py`
**Связанные компоненты:**
- 🔗 `functools`

### 📄 `venv\Lib\site-packages\pip\_internal\req\req_uninstall.py`
**Связанные компоненты:**
- 🔗 `functools`

### 📄 `venv\Lib\site-packages\pip\_internal\resolution\legacy\resolver.py`
**Связанные компоненты:**
- 🔗 `itertools`

### 📄 `venv\Lib\site-packages\pip\_internal\resolution\resolvelib\factory.py`
**Связанные компоненты:**
- 🔗 `functools`

### 📄 `venv\Lib\site-packages\pip\_internal\resolution\resolvelib\found_candidates.py`
**Связанные компоненты:**
- 🔗 `functools`

### 📄 `venv\Lib\site-packages\pip\_internal\resolution\resolvelib\provider.py`
**Связанные компоненты:**
- 🔗 `functools`

### 📄 `venv\Lib\site-packages\pip\_internal\resolution\resolvelib\resolver.py`
**Связанные компоненты:**
- 🔗 `functools`

### 📄 `venv\Lib\site-packages\pip\_internal\utils\entrypoints.py`
**Связанные компоненты:**
- 🔗 `itertools`

### 📄 `venv\Lib\site-packages\pip\_internal\utils\misc.py`
**Связанные компоненты:**
- 🔗 `itertools`
- 🔗 `functools`

### 📄 `venv\Lib\site-packages\pip\_internal\utils\packaging.py`
**Связанные компоненты:**
- 🔗 `functools`

### 📄 `venv\Lib\site-packages\pip\_internal\utils\retry.py`
**Связанные компоненты:**
- 🔗 `functools`

### 📄 `venv\Lib\site-packages\pip\_internal\utils\temp_dir.py`
**Связанные компоненты:**
- 🔗 `itertools`

### 📄 `venv\Lib\site-packages\pip\_internal\utils\_jaraco_text.py`
**Связанные компоненты:**
- 🔗 `itertools`
- 🔗 `functools`

### 📄 `venv\Lib\site-packages\pip\_vendor\typing_extensions.py`
**Связанные компоненты:**
- 🔗 `functools`

### 📄 `venv\Lib\site-packages\pip\_vendor\cachecontrol\adapter.py`
**Связанные компоненты:**
- 🔗 `functools`

### 📄 `venv\Lib\site-packages\pip\_vendor\distlib\locators.py`
**Связанные компоненты:**
- 🔗 `.database`

### 📄 `venv\Lib\site-packages\pip\_vendor\distlib\wheel.py`
**Связанные компоненты:**
- 🔗 `.database`

### 📄 `venv\Lib\site-packages\pip\_vendor\packaging\specifiers.py`
**Связанные компоненты:**
- 🔗 `itertools`

### 📄 `venv\Lib\site-packages\pip\_vendor\packaging\version.py`
**Связанные компоненты:**
- 🔗 `itertools`

### 📄 `venv\Lib\site-packages\pip\_vendor\packaging\_manylinux.py`
**Связанные компоненты:**
- 🔗 `functools`

### 📄 `venv\Lib\site-packages\pip\_vendor\packaging\_musllinux.py`
**Связанные компоненты:**
- 🔗 `functools`

### 📄 `venv\Lib\site-packages\pip\_vendor\pkg_resources\__init__.py`
**Связанные компоненты:**
- 🔗 `functools`

### 📄 `venv\Lib\site-packages\pip\_vendor\platformdirs\android.py`
**Связанные компоненты:**
- 🔗 `functools`

### 📄 `venv\Lib\site-packages\pip\_vendor\platformdirs\windows.py`
**Связанные компоненты:**
- 🔗 `functools`

### 📄 `venv\Lib\site-packages\pip\_vendor\pygments\regexopt.py`
**Связанные компоненты:**
- 🔗 `itertools`

### 📄 `venv\Lib\site-packages\pip\_vendor\pygments\formatters\html.py`
**Связанные компоненты:**
- 🔗 `functools`

### 📄 `venv\Lib\site-packages\pip\_vendor\resolvelib\resolvers.py`
**Связанные компоненты:**
- 🔗 `itertools`

### 📄 `venv\Lib\site-packages\pip\_vendor\resolvelib\structs.py`
**Связанные компоненты:**
- 🔗 `itertools`

### 📄 `venv\Lib\site-packages\pip\_vendor\rich\align.py`
**Связанные компоненты:**
- 🔗 `itertools`

### 📄 `venv\Lib\site-packages\pip\_vendor\rich\cells.py`
**Связанные компоненты:**
- 🔗 `functools`

### 📄 `venv\Lib\site-packages\pip\_vendor\rich\color.py`
**Связанные компоненты:**
- 🔗 `functools`

### 📄 `venv\Lib\site-packages\pip\_vendor\rich\columns.py`
**Связанные компоненты:**
- 🔗 `itertools`

### 📄 `venv\Lib\site-packages\pip\_vendor\rich\console.py`
**Связанные компоненты:**
- 🔗 `itertools`
- 🔗 `functools`

### 📄 `venv\Lib\site-packages\pip\_vendor\rich\containers.py`
**Связанные компоненты:**
- 🔗 `itertools`

### 📄 `venv\Lib\site-packages\pip\_vendor\rich\layout.py`
**Связанные компоненты:**
- 🔗 `itertools`

### 📄 `venv\Lib\site-packages\pip\_vendor\rich\palette.py`
**Связанные компоненты:**
- 🔗 `functools`

### 📄 `venv\Lib\site-packages\pip\_vendor\rich\pretty.py`
**Связанные компоненты:**
- 🔗 `itertools`

### 📄 `venv\Lib\site-packages\pip\_vendor\rich\progress_bar.py`
**Связанные компоненты:**
- 🔗 `functools`

### 📄 `venv\Lib\site-packages\pip\_vendor\rich\repr.py`
**Связанные компоненты:**
- 🔗 `functools`

### 📄 `venv\Lib\site-packages\pip\_vendor\rich\segment.py`
**Связанные компоненты:**
- 🔗 `itertools`
- 🔗 `functools`

### 📄 `venv\Lib\site-packages\pip\_vendor\rich\style.py`
**Связанные компоненты:**
- 🔗 `functools`

### 📄 `venv\Lib\site-packages\pip\_vendor\rich\text.py`
**Связанные компоненты:**
- 🔗 `functools`

### 📄 `venv\Lib\site-packages\pip\_vendor\tomli\_re.py`
**Связанные компоненты:**
- 🔗 `functools`

### 📄 `venv\Lib\site-packages\pip\_vendor\urllib3\poolmanager.py`
**Связанные компоненты:**
- 🔗 `functools`

### 📄 `venv\Lib\site-packages\pip\_vendor\urllib3\contrib\_securetransport\low_level.py`
**Связанные компоненты:**
- 🔗 `itertools`

### 📄 `venv\Lib\site-packages\pip\_vendor\urllib3\packages\six.py`
**Связанные компоненты:**
- 🔗 `itertools`
- 🔗 `functools`

### 📄 `venv\Lib\site-packages\pip\_vendor\urllib3\packages\backports\weakref_finalize.py`
**Связанные компоненты:**
- 🔗 `itertools`

### 📄 `venv\Lib\site-packages\pip\_vendor\urllib3\util\retry.py`
**Связанные компоненты:**
- 🔗 `itertools`

### 📄 `venv\Lib\site-packages\pip\_vendor\urllib3\util\wait.py`
**Связанные компоненты:**
- 🔗 `functools`
