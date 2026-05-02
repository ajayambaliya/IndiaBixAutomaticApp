# WhatsApp Daily PDF Bot (Free & Automatic)

This project allows you to send a daily PDF to specific WhatsApp groups using GitHub Actions for free.

## Setup Instructions

### 1. Local Configuration
1. Place the PDF you want to send in this folder and rename it to `document.pdf`.
2. Open your terminal in this folder.
3. Run the setup script to link your WhatsApp:
   ```bash
   node setup.js
   ```
4. Scan the QR code with your WhatsApp (Linked Devices).
5. Once it says "Client is ready!", close the script (Ctrl+C).

### 2. Prepare the Session for GitHub
You need to convert the session folder into a string that GitHub can use. Run this command in your terminal:

**Windows (PowerShell):**
```powershell
Compress-Archive -Path .wwebjs_auth -DestinationPath session.zip -Force; [Convert]::ToBase64String([IO.File]::ReadAllBytes('session.zip')) | Out-File -FilePath session_base64.txt; Remove-Item session.zip
```

**What this does:**
- Zips the `.wwebjs_auth` folder.
- Converts it to a long Base64 string.
- Saves it in `session_base64.txt`.

### 3. GitHub Secrets
1. Create a **Private** repository on GitHub and push this code.
2. Go to **Settings > Secrets and variables > Actions**.
3. Add the following secrets:
   - `WWEBJS_SESSION`: Copy the entire content of `session_base64.txt`.
   - `WHATSAPP_GROUPS`: A comma-separated list of group names (e.g., `Family Group,Office Updates`).

### 4. How it works
- The bot runs automatically every day at **4:00 AM UTC** (9:30 AM IST).
- You can manually trigger it from the **Actions** tab in your GitHub repository.

## Important Notes
- **Privacy**: Keep your repository **PRIVATE**. The `WWEBJS_SESSION` gives full access to your WhatsApp.
- **Cost**: This setup is 100% free using GitHub Actions free tier.
- **Maintenance**: If the session expires or you log out from your phone, you will need to repeat Step 1 and update the `WWEBJS_SESSION` secret.
