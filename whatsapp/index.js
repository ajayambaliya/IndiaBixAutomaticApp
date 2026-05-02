const { Client, RemoteAuth, LocalAuth, MessageMedia } = require('whatsapp-web.js');
const { MongoStore } = require('wwebjs-mongo');
const mongoose = require('mongoose');
const fs = require('fs');
const path = require('path');
require('dotenv').config({ path: path.join(__dirname, '../.env') });
require('dotenv').config();

// Dynamic arguments from command line
const args = process.argv.slice(2);
const PDF_PATH = args[0] ? path.resolve(args[0]) : path.join(__dirname, 'document.pdf');
const GROUP_NAMES = process.env.WHATSAPP_GROUPS ? process.env.WHATSAPP_GROUPS.split(',') : [];

if (!fs.existsSync(PDF_PATH)) {
    console.error(`Error: PDF file not found at ${PDF_PATH}`);
    process.exit(1);
}

async function start() {
    const clientId = "whatsapp-bot";
    const sessionDir = path.join(__dirname, `.wwebjs_auth/session-${clientId}`);
    const mongoUri = process.env.MONGO_DB_URI;

    if (mongoUri) {
        console.log('Using MongoDB for manual session retrieval...');
        try {
            await mongoose.connect(mongoUri);
            const SessionModel = mongoose.models.WhatsAppSession || mongoose.model('WhatsAppSession', new mongoose.Schema({
                id: String,
                session: Buffer
            }, { collection: 'whatsapp_sessions' }));

            const sessionData = await SessionModel.findOne({ id: clientId });
            if (sessionData) {
                console.log(`🔍 Found session in MongoDB (${(sessionData.session.length/1024).toFixed(2)} KB). Extracting...`);
                
                // Ensure local dir is clean
                if (fs.existsSync(sessionDir)) fs.rmSync(sessionDir, { recursive: true, force: true });
                fs.mkdirSync(sessionDir, { recursive: true });

                // Unzip manually
                const unzipper = require('unzipper');
                const stream = require('stream');
                const bufferStream = new stream.PassThrough();
                bufferStream.end(sessionData.session);
                
                await bufferStream.pipe(unzipper.Extract({ path: sessionDir })).promise();
                console.log('✅ Session extracted successfully.');
            } else {
                console.log('⚠️ No session found in MongoDB.');
            }
        } catch (err) {
            console.error('❌ Failed manual session retrieval:', err);
        }
    }

    const client = new Client({
        authStrategy: new LocalAuth({
            clientId: clientId,
            dataPath: './.wwebjs_auth'
        }),
        puppeteer: {
            headless: true,
            args: [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-extensions',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--no-first-run',
                '--no-zygote',
                '--disable-gpu'
            ],
            userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
    });

    console.log('Initializing WhatsApp client...');

    client.on('loading_screen', (percent, message) => {
        console.log('LOADING SCREEN', percent, message);
    });

    client.on('qr', (qr) => {
        if (process.env.GITHUB_ACTIONS || process.argv.includes('--github-actions')) {
            console.error('❌ SESSION EXPIRED: WhatsApp session is no longer valid.');
            console.error('👉 ACTION REQUIRED: Run "node whatsapp/setup.js" on your computer to re-pair.');
            process.exit(1); // Fail the build to stop wasting minutes
        }
        
        console.log('QR RECEIVED. Scan again:');
        const qrcode = require('qrcode-terminal');
        qrcode.generate(qr, { small: true });
    });

    client.on('authenticated', () => {
        console.log('AUTHENTICATED');
    });

    client.on('remote_session_saved', () => {
        console.log('REMOTE SESSION SAVED');
    });

    client.on('auth_failure', (msg) => {
        console.error('AUTHENTICATION FAILURE:', msg);
        process.exit(1);
    });

    let isBroadcasting = false;
    client.on('ready', async () => {
        if (isBroadcasting) return;
        isBroadcasting = true;

        console.log('Bot is ready! Starting Resilient Broadcast Engine...');
        
        let attempts = 0;
        const maxAttempts = 5;
        let chats = null;

        while (attempts < maxAttempts) {
            try {
                attempts++;
                console.log(`📡 stability Check (Attempt ${attempts}/${maxAttempts})...`);
                await new Promise(resolve => setTimeout(resolve, 15000)); // Wait 15s for WhatsApp to settle

                chats = await client.getChats();
                if (chats && chats.length > 0) break; 
            } catch (err) {
                console.error(`⚠️ Stability check failed: ${err.message}. Retrying in 10s...`);
                await new Promise(resolve => setTimeout(resolve, 10000));
            }
        }

        if (!chats) {
            console.error('❌ Failed to stabilize WhatsApp after multiple attempts. Exiting.');
            process.exit(1);
        }

        // PREMIUM DYNAMIC CAPTION
        const dateStr = path.basename(PDF_PATH).match(/\d{4}-\d{2}-\d{2}/)?.[0] || new Date().toISOString().split('T')[0];
        const formattedDate = new Date(dateStr).toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' });

        const CUSTOM_CAPTION = `📅 *Daily Current Affairs • ${formattedDate}* 📝\n\n` +
            `🚀 *What's inside?*\n` +
            `✅ Verified MCQ Questions\n` +
            `✅ Detailed Deep-Dive Explanations\n` +
            `✅ Exam-Oriented Highlights\n\n` +
            `💡 *Knowledge is Power. Stay Ahead!*\n` +
            `✨ _Curated with ❤️ by Ajay Ambaliya_ ✨`;

        const media = MessageMedia.fromFilePath(PDF_PATH);
        
        // Filter groups
        const targetGroups = chats.filter(chat => 
            chat.isGroup && 
            GROUP_NAMES.map(gn => gn.trim()).includes(chat.name.trim())
        );

        console.log(`✅ Found ${targetGroups.length} matching groups. Starting broadcast...`);

        for (let i = 0; i < targetGroups.length; i++) {
            const group = targetGroups[i];
            try {
                console.log(`[${i + 1}/${targetGroups.length}] Sending PDF to: ${group.name}...`);
                await client.sendMessage(group.id._serialized, media, { caption: CUSTOM_CAPTION });
                console.log(`✔️ Sent to ${group.name}`);
                await new Promise(resolve => setTimeout(resolve, Math.random() * 5000 + 5000));
            } catch (err) {
                console.error(`❌ Failed to send to ${group.name}:`, err.message);
            }
        }

        console.log('🌟 ALL BROADCAST TASKS COMPLETED!');
        setTimeout(async () => {
            console.log('Shutting down gracefully...');
            await client.destroy();
            process.exit(0);
        }, 10000);
    });

    console.log('Starting client initialization... (This may take up to 2 minutes)');
    client.initialize().catch(err => console.error('Initialization error:', err));
}

start().catch(err => {
    console.error('Main loop error:', err);
    process.exit(1);
});
