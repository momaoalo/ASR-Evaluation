# ASR Evaluation — دليل التشغيل (Windows)

تطبيق محلي لمقارنة نصوص تحويل الكلام إلى كتابة باستخدام WER وCER وتحليل الاستبدال والحذف والإضافة.

## تشغيل المشروع لأول مرة

افتح **PowerShell عادي** (لا تبدأ من `C:\Windows\System32`) ثم نفّذ:

```powershell
cd "$env:USERPROFILE\Documents"
git clone https://github.com/momaoalo/ASR-Evaluation.git
cd .\ASR-Evaluation
.\SETUP_WINDOWS.bat
.\START_WINDOWS.bat
```

يفتح التطبيق على <http://127.0.0.1:5000>. سكربت الإعداد ينشئ `.venv` ويثبت Flask وWaitress وHUMAIN SDK و`yt-dlp[default]` وبقية مكتبات Python؛ **لا تحتاج تفعيل البيئة بنفسك**. ملف البدء يستخدم Python الموجود داخل `.venv`.

## تحديث نسخة موجودة

إذا كان اسم النسخة التجريبية عندك `ASR-Evaluation-Test`:

```powershell
cd "$env:USERPROFILE\Documents\ASR-Evaluation-Test"
git pull --ff-only
.\SETUP_WINDOWS.bat
.\START_WINDOWS.bat
```

لا تثبّت المكتبات باستخدام `python` العام من مجلد آخر. وللتشغيل اليدوي استخدم:

```powershell
.\.venv\Scripts\python.exe run_local.py
```

## التجربة بالصوت وYouTube

- **رفع صوت / تشغيل API فعلي:** يلزم FFmpeg وFFprobe، وثبتهما عبر `winget install -e --id Gyan.FFmpeg`.
- **رابط YouTube:** `yt-dlp` يُثبّت تلقائيًا ضمن مكتبات المشروع. ثبّت Deno (موصى به) بالأمر `winget install -e --id DenoLand.Deno`.
- أغلق PowerShell وافتحه مجددًا بعد تثبيت FFmpeg أو Deno.

فحص سريع:

```powershell
ffmpeg -version
ffprobe -version
deno --version
.\.venv\Scripts\python.exe -m yt_dlp --version
.\.venv\Scripts\python.exe diagnose.py
```

قد ترفض YouTube بعض المقاطع؛ ارفع ملفًا صوتيًا من جهازك بدلًا منها.

## لا تخلط النتائج التجريبية مع API

**View sample results / Supplied transcripts** تقارن نصوصًا محفوظة فقط، **بدون** استدعاء API. النموذج الأول في المثال القديم غير معروف المصدر، ولا يجوز نسبه إلى HUMAIN. ملف الصوت الأصلي للعينة غير موجود في نسخة GitHub العامة.

للمقارنة الحقيقية: **New evaluation → Upload أو YouTube URL → Ground Truth → HUMAIN / ElevenLabs → Model connections**. أدخل مفاتيحك في الواجهة، ورابط حساب HUMAIN الصحيح، وألغِ تفعيل **Use supplied transcripts** ووافق على إرسال الصوت. قد تستهلك الطلبات رصيد API. لا ترسل المفاتيح لأحد ولا ترفعها إلى GitHub.

## حلول المشاكل التي واجهتنا

| المشكلة | الحل |
|---|---|
| `Permission denied` عند `git clone` | انتقل إلى مجلد Documents بدل `C:\Windows\System32` |
| `No module named waitress` | `SETUP_WINDOWS.bat` ثم شغل باستخدام `.venv\Scripts\python.exe` |
| `yt-dlp was not found` | `git pull` ثم `SETUP_WINDOWS.bat`؛ المكتبة صارت ضمن المتطلبات |
| فشل تجهيز الصوت | ثبّت FFmpeg وFFprobe وتأكد من تعرف النظام عليهما |
| `Incomplete application files` | تأكد من تحديث نسخة Git نظيفة؛ ملف `.gitattributes` يمنع تغيير نهايات أسطر الواجهة |
| نتائج `supplied` تظهر في المقارنة | هذه بيانات محفوظة وليست تشغيلًا فعليًا للمزود |

التحقق من الواجهة عبر `/api/build` أو `verify_ui_files`؛ الأمر `python verify_package.py` يفحص الآن ملفات تشغيل GitHub وبصمات الواجهة الحالية. خيار `--full-release` فقط لفحص أرشيف ZIP الأصلي المختلف عن النسخة العامة.

[English README](README.md) · [بنية النظام](docs/ARCHITECTURE.md) · [إعدادات الربط](docs/portfolio/CONFIGURATION.md)
