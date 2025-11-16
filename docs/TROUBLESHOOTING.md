# Troubleshooting Guide

## LanguageTool Issues

### NoClassDefFoundError: org.languagetool.gui.Configuration

**Symptoms:**
```
language_tool_python.utils.LanguageToolError: Error: Internal Error: 
java.lang.NoClassDefFoundError: Could not initialize class org.languagetool.gui.Configuration
```

**Cause:** Corrupted or incomplete LanguageTool cache (often a SNAPSHOT version with bugs).

**Solution:**
```bash
# Clear the LanguageTool cache and let it re-download
rm -rf ~/.cache/language_tool_python/
```

### UnsatisfiedLinkError: Can't load library libawt_xawt.so

**Symptoms:**
```
java.lang.UnsatisfiedLinkError: Can't load library: /usr/lib/jvm/java-17-openjdk-amd64/lib/libawt_xawt.so
```

**Cause:** Java is trying to load GUI (AWT/X11) libraries in a headless environment.

**Solution:** Run Java in headless mode by setting the `JAVA_TOOL_OPTIONS` environment variable:
```bash
export JAVA_TOOL_OPTIONS="-Djava.awt.headless=true"
```

This is already configured in `.devcontainer/devcontainer.json` via the `containerEnv` setting, so it should work automatically in the dev container after rebuild.

### LanguageTool can't find en-GB dictionary

**Answer:** This is usually a misleading error message. The en-GB dictionary is included in the standard LanguageTool download. The actual issue is typically one of the above errors (Java GUI libraries or corrupted cache).

**Verification:** Check if the en-GB rules exist:
```bash
ls ~/.cache/language_tool_python/LanguageTool-*/org/languagetool/rules/en/en-GB/
```

You should see files like `grammar.xml`, `replace.txt`, and `style.xml`.

### Connection Reset / Connection Aborted on Large Documents

**Symptoms:**
```
ConnectionResetError: [Errno 104] Connection reset by peer
language_tool_python.utils.LanguageToolError: http://127.0.0.1:8081/v2/: ('Connection aborted.', ConnectionResetError(104, 'Connection reset by peer'))
```

**Cause:** Large documents (>300KB) exceed HTTP GET request URL length limits.

**Solution:** ✅ **FIXED** - The codebase now uses a POST request monkey-patch (`src/language_check/language_tool_patch.py`) that automatically handles large documents. This fix is applied when the language_check module is imported.

**Details:** See [docs/LANGUAGE_CHECK_POST_FIX.md](./LANGUAGE_CHECK_POST_FIX.md) for the full technical explanation and implementation details.

## Python Environment Issues

### Module not found errors

**Solution:** Always use `uv` to run commands:
```bash
uv run python -m src.language_check.language_check
```

See [docs/UV_GUIDE.md](./UV_GUIDE.md) for more details on using `uv`.
