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
const CUSTOM_CAPTION = args[1] || 'Here is your daily PDF!';
const GROUP_NAMES = process.env.WHATSAPP_GROUPS ? process.env.WHATSAPP_GROUPS.split(',') : [];

if (!fs.existsSync(PDF_PATH)) {
    console.error(`Error: PDF file not found at ${PDF_PATH}`);
    process.exit(1);
}

async function start() {
    let authStrategy;
    const mongoUri = process.env.MONGO_DB_URI;
    
    if (mongoUri) {
        console.log('Using MongoDB for session storage (database: indiabixauto)...');
        try {
            await mongoose.connect(mongoUri);
            const store = new MongoStore({ mongoose: mongoose, collection: 'whatsapp_sessions' });
            authStrategy = new RemoteAuth({
                store: store,
                backupSyncIntervalMs: 600000,
                clientId: "whatsapp-bot",
                dataPath: './.wwebjs_auth'
            });
        } catch (err) {
            console.error('Failed to connect to MongoDB, falling back to LocalAuth:', err);
            authStrategy = new LocalAuth({ clientId: "whatsapp-bot" });
        }
    } else {
        console.log('No MONGO_DB_URI found, using LocalAuth...');
        authStrategy = new LocalAuth({ clientId: "whatsapp-bot" });
    }

    const client = new Client({
        authStrategy: authStrategy,
        puppeteer: {
            headless: true,
            args: [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36'
            ]
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

    client.on('ready', async () => {
        console.log('Bot is ready!');

        const media = MessageMedia.fromFilePath(PDF_PATH);
        const chats = await client.getChats();
        
        // Get all group names to help debugging
        const allGroups = chats.filter(c => c.isGroup).map(c => c.name);
        console.log('Found these groups in your WhatsApp:', allGroups.join(', '));

        const targetGroups = chats.filter(chat => 
            chat.isGroup && 
            GROUP_NAMES.map(gn => gn.trim()).includes(chat.name.trim())
        );

        console.log(`Found ${targetGroups.length} matching groups. Starting broadcast with safety delays...`);

        // Helper function for delays
        const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

        for (let i = 0; i < targetGroups.length; i++) {
            const group = targetGroups[i];
            try {
                console.log(`[${i + 1}/${targetGroups.length}] Sending PDF to: ${group.name}...`);
                await client.sendMessage(group.id._serialized, media, { caption: CUSTOM_CAPTION });
                console.log(`✅ Sent to ${group.name}`);

                // Random delay between 5 to 12 seconds to mimic human behavior
                if (i < targetGroups.length - 1) {
                    const delay = Math.floor(Math.random() * (12000 - 5000 + 1)) + 5000;
                    console.log(`Sleeping for ${Math.round(delay/1000)}s to avoid ban...`);
                    await sleep(delay);
                }
            } catch (err) {
                console.error(`❌ Failed to send PDF to ${group.name}:`, err);
            }
        }

        console.log('All broadcast tasks completed successfully!');

        console.log('Waiting for messages to be delivered...');
        // Give it more time to ensure the media is fully uploaded and sent
        setTimeout(async () => {
            console.log('Closing WhatsApp client...');
            await client.destroy();
            process.exit(0);
        }, 15000);
    });

    console.log('Starting client initialization... (This may take up to 2 minutes)');
    client.initialize().catch(err => console.error('Initialization error:', err));
}

start().catch(err => {
    console.error('Main loop error:', err);
    process.exit(1);
});
