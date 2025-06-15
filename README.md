# Current Affairs PDF Generator

Automatically scrape current affairs from IndiaBix, generate beautiful PDFs, and send them to Telegram channels.

## Recent Fixes

* 🔄 **Fixed Import Paths**: Updated import paths in main.py to correctly reference modules
* 🔄 **GitHub Actions Workflow**: Updated workflow file to use correct paths and latest artifact upload action
* 🔄 **Environment Setup**: Added proper .env file configuration

## Features

* 🔍 **Automated Scraping**: Daily scrapes current affairs from IndiaBix
* 📊 **MongoDB Integration**: Stores questions and tracks processed URLs
* 📱 **Multi-language Support**: Generates PDFs in English and Gujarati
* 🤖 **Telegram Integration**: Automatically sends PDFs to configured channels
* 🔄 **GitHub Actions**: Runs daily at 7:30 AM IST
* 🎨 **Beautiful Design**: Modern, responsive PDF layout
* 🔁 **URL Tracking**: Automatically skips already processed URLs to avoid duplicates

## Setup Instructions

### Prerequisites

* Python 3.8+
* MongoDB (local or Atlas)
* Telegram Bot Token (for sending PDFs to channels)

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/ajayambaliya/IndiaBixAuto.git
   cd IndiaBixAuto
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Install Playwright browsers:
   ```bash
   playwright install chromium
   ```

4. Create a `.env` file with the following variables:
   ```
   MONGO_DB_URI=mongodb://localhost:27017/
   TELEGRAM_BOT_TOKEN=your_bot_token
   ENGLISH_CHANNEL=@your_english_channel
   GUJARATI_CHANNEL=@your_gujarati_channel
   ```

### Usage

#### Generate PDFs for a specific date

```bash
python main.py --date 2023-09-20 --languages en gu
```

#### Generate PDFs from a specific URL

```bash
python main.py --url "https://www.indiabix.com/current-affairs/2023-09-20/" --languages en
```

#### Generate PDFs and send to Telegram

```bash
python main.py --date 2023-09-20 --languages en gu --send-telegram
```

#### Run in GitHub Actions mode (skips already processed URLs)

```bash
python main.py --month 2023-09 --languages en gu --github-actions
```

### Utility Scripts

The project includes several utility scripts in the `scripts` directory:

#### Mark URLs as processed

This script marks a range of URLs as already processed in MongoDB, useful for testing:

```bash
python scripts/mark_urls_as_scraped.py 2023-09-01 2023-09-25
```

For more details, see the [scripts README](scripts/README.md).

## GitHub Actions Deployment

The project includes a GitHub Actions workflow that runs daily at 7:30 AM IST. To set it up:

1. Add the following secrets to your GitHub repository:
   - `MONGO_DB_URI`: Your MongoDB connection string
   - `TELEGRAM_BOT_TOKEN`: Your Telegram bot token
   - `ENGLISH_CHANNEL`: Your English Telegram channel ID (e.g., @daily_current_all_source)
   - `GUJARATI_CHANNEL`: Your Gujarati Telegram channel ID (e.g., @currentadda)

2. The workflow will:
   - Run at 7:30 AM IST every day
   - Scrape the current day's content
   - Generate PDFs in both languages
   - Send PDFs to respective Telegram channels
   - Upload PDFs as GitHub artifacts

## Customization

### Modifying Templates

The PDF templates are located in the `src/templates` directory:
- `base.html`: Main template structure
- `cover_page.html`: Cover page design
- `categories.html`: Categories page design

### Adding New Languages

To add a new language:
1. Update the `src/core/translator.py` file
2. Add language-specific templates and translations
3. Include the new language code in the `--languages` parameter

## Troubleshooting

- **MongoDB Connection Issues**: Verify your connection string and network access
- **PDF Generation Errors**: Check Playwright installation and browser dependencies
- **Telegram Sending Failures**: Verify bot token and ensure the bot is an admin in the channels

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgements

- [IndiaBix](https://www.indiabix.com/) for providing current affairs content
- Created by Ajay Ambaliya 