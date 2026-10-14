# Orbit AI Content and Image Generation

Orbit uses two hosted providers through its local server:

- **Gemini 3.5 Flash-Lite** writes campaign text with minimal reasoning for faster drafts.
- **Cloudflare Workers AI FLUX.2 Klein 4B** creates campaign images.

The browser talks only to the local Orbit server. Provider credentials are entered when Orbit starts, kept in that server process, and removed when it exits. They are not saved in the project or web page.

## One-time setup

1. Create a Gemini API key in [Google AI Studio](https://aistudio.google.com/apikey). Google controls the Gemini free-tier availability and limits for the project; check your AI Studio usage before relying on it.
2. Create or sign in to a Cloudflare account. In its dashboard, find your **Account ID** and create an API token allowed to run Workers AI. Keep the account on the **Workers Free** plan if you want to use only the no-charge allocation.
3. Install Python 3 if it is not already installed.

Do not paste either key into Orbit’s webpage, chat, or a source file. Do not add paid billing if you want to avoid charges.

## Start Orbit

1. In this folder, run `Start-Agent.cmd` (or right-click `Start-Agent.ps1` and choose **Run with PowerShell**).
2. Enter your Gemini key at the hidden prompt, then the Cloudflare Account ID and Workers AI API token at their prompts.
3. Orbit opens at `http://127.0.0.1:8765`.
4. Use **AI Content Agent** for campaign copy, audience angles, and suggestions informed by the selected Digital Twin’s synthetic profile and topic-interest scores. Use **AI Image Generator** to create and download an image with Cloudflare, then add the artwork to the Content Calendar or send the campaign to the Digital Twin.
5. Close Orbit with Ctrl+C in its server window. The credentials are cleared when the server exits.

If a provider rejects a key, recheck the account, model access, token permissions, and remaining free quota. Orbit does not switch to a paid provider when a free limit is reached.

## Free usage limits

Cloudflare Workers AI currently includes **10,000 Neurons per day** on Workers Free. This allowance is shared across Workers AI activity on the account, resets daily at 00:00 UTC, and requests fail after it is used. The number of images varies with the model and output size, so Orbit does not promise a fixed daily image count. Keep the account on Workers Free; Cloudflare bills usage above the allowance if the account is on Workers Paid.

Gemini’s free-tier access and limits depend on the model and Google AI Studio project. Google can change these limits. Orbit reports a free quota error and does not fall back to a paid model.

## Project files

- `orbit-campaign-twin-prototype.html` — website
- `agent_server.py` — local web server and Gemini/Cloudflare request proxy
- `Start-Agent.ps1` / `Start-Agent.cmd` — credential prompts and server launcher
- `trained-model.js` — synthetic audience clusters, six fitted topic classifiers, and per-cluster prediction scores
- `train_audience_model.py` — rebuilds classifier weights, cluster predictions, and holdout metrics from the included dataset
- `social_campaign_audience_dataset.xlsx` — synthetic audience dataset
- `acai-bowl-campaign-visual.png` — sample campaign visual
- `orbit-by-205-logo.png` — Orbit by 205 logo

The audience clusters and classifier use synthetic data, not real campaign outcomes. Their scores are a classroom demonstration. The content agent drafts suggestions; verify product details and claims before publishing. Posts and artwork are saved to this browser’s local calendar; Orbit does not publish to social platforms.

To retrain the topic classifiers after changing the dataset, run `python train_audience_model.py` from this folder. The script makes a deterministic stratified 80/20 split for each topic, fits feature scaling on training rows only, trains six L2-regularized logistic regressions, and writes their holdout metrics and representative-cluster predictions to `trained-model.js`. Each classifier excludes its own answer label from its input features. The reported metrics should not be interpreted as expected campaign performance.

## Official references

- [Gemini API models](https://ai.google.dev/gemini-api/docs/models)
- [Gemini API pricing and free tier](https://ai.google.dev/gemini-api/docs/pricing)
- [Google AI Studio API keys](https://aistudio.google.com/apikey)
- [Cloudflare Workers AI pricing and daily free allocation](https://developers.cloudflare.com/workers-ai/platform/pricing/)
- [Cloudflare FLUX.2 Klein 4B request format](https://developers.cloudflare.com/changelog/post/2026-01-15-flux-2-klein-4b-workers-ai/)
