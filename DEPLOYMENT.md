# Deployment Guide

This guide will help you set up the Current Affairs PDF Generator for automated daily operation using GitHub Actions.

## Prerequisites

1. A GitHub account
2. A MongoDB database (Atlas free tier works well)
3. A Telegram bot token (create one via [@BotFather](https://t.me/botfather))
4. Telegram channels where your bot is an administrator

## Step 1: Fork or Clone the Repository

Fork this repository to your own GitHub account or create a new repository and push the code there.

## Step 2: Set Up GitHub Secrets

1. Go to your repository on GitHub
2. Navigate to **Settings** > **Secrets and variables** > **Actions**
3. Click on **New repository secret**
4. Add the following secrets:

   - `MONGO_DB_URI`: Your MongoDB connection string
     - Example: `mongodb+srv://username:password@cluster.mongodb.net/currentaffairs`
   
   - `TELEGRAM_BOT_TOKEN`: Your Telegram bot token
     - Example: `1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZ`
   
   - `ENGLISH_CHANNEL`: Your English Telegram channel ID
     - Example: `@daily_current_all_source`
   
   - `GUJARATI_CHANNEL`: Your Gujarati Telegram channel ID
     - Example: `@currentadda`

## Step 3: Enable GitHub Actions

1. Go to the **Actions** tab in your repository
2. GitHub will detect the workflow file in `.github/workflows/daily_scraper.yml`
3. Click on **I understand my workflows, go ahead and enable them**

## Step 4: Test the Workflow Manually

1. Go to the **Actions** tab
2. Select the **Daily Current Affairs Scraper** workflow
3. Click on **Run workflow**
4. Choose the **main** branch
5. Click on **Run workflow**

This will trigger the workflow manually. You can monitor its progress in the Actions tab.

## Step 5: Verify the Results

After the workflow completes:

1. Check your Telegram channels for the PDF files
2. Verify that the PDFs contain the expected content
3. Check the workflow logs for any errors or warnings

## Step 6: Customize the Workflow (Optional)

You can customize the workflow by editing the `.github/workflows/daily_scraper.yml` file:

- Change the schedule to run at a different time
- Modify the languages generated
- Add additional steps or notifications

### Changing the Schedule

The default schedule runs at 7:30 AM IST (2:00 AM UTC). To change this, modify the cron expression:

```yaml
schedule:
  # Format: minute hour day_of_month month day_of_week
  - cron: '0 2 * * *'  # 2:00 AM UTC = 7:30 AM IST
```

## Troubleshooting

### Workflow Failures

If the workflow fails:

1. Check the workflow logs for error messages
2. Verify that your MongoDB connection is working
3. Ensure your Telegram bot has admin privileges in the channels
4. Try running the test script locally to debug issues:

```bash
cd modern_pdf_generator
python test_workflow.py
```

### MongoDB Issues

- Ensure your IP is whitelisted in MongoDB Atlas
- Check that your database user has the correct permissions
- Verify the connection string format

### Telegram Issues

- Make sure the bot is an administrator in the channels
- Check that the channel IDs are correct (they should start with @)
- Verify that the bot token is valid

## Monitoring and Maintenance

- Check the workflow runs daily in the Actions tab
- Monitor your MongoDB storage usage
- Periodically update dependencies to keep the system secure

## Additional Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [MongoDB Atlas Documentation](https://docs.atlas.mongodb.com/)
- [Telegram Bot API Documentation](https://core.telegram.org/bots/api) 