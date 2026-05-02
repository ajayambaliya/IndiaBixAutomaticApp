const mongoose = require('mongoose');
const { MongoStore } = require('wwebjs-mongo');
const fs = require('fs');
const path = require('path');
require('dotenv').config({ path: path.join(__dirname, '../.env') });

async function forceSync() {
    const mongoUri = "mongodb+srv://dalal:Hjeh3T3ZibiN8IiX@cluster0.cqll1b7.mongodb.net/indiabixauto?retryWrites=true&w=majority";
    
    console.log('Connecting to MongoDB database: "indiabixauto"...');
    await mongoose.connect(mongoUri);
    const store = new MongoStore({ mongoose: mongoose });

    console.log('Using Collection: "whatsapp_sessions"');

    const clientId = "whatsapp-bot";
    const sessionDir = path.join(__dirname, `.wwebjs_auth/RemoteAuth-${clientId}`);

    if (!fs.existsSync(sessionDir)) {
        console.error(`❌ No local session found at ${sessionDir}`);
        return;
    }

    console.log('Cleaning browser cache to shrink session size...');
    const junkFolders = [
        'Default/Cache',
        'Default/Code Cache',
        'Default/GPUCache',
        'Default/Service Worker/CacheStorage',
        'Default/Service Worker/ScriptCache'
    ];

    junkFolders.forEach(folder => {
        const fullPath = path.join(sessionDir, folder);
        if (fs.existsSync(fullPath)) {
            try {
                fs.rmSync(fullPath, { recursive: true, force: true });
                console.log(`  🧹 Deleted ${folder}`);
            } catch (e) {
                console.log(`  ⚠️ Could not delete ${folder} (might be in use)`);
            }
        }
    });

    console.log('Pushing cleaned session to MongoDB...');
    
    try {
        const archiver = require('archiver');
        const { Buffer } = require('buffer');
        
        // Create a temporary zip in memory
        const chunks = [];
        const archive = archiver('zip', { zlib: { level: 9 } });

        archive.on('data', (chunk) => chunks.push(chunk));
        
        console.log('Zipping session folder...');
        archive.directory(sessionDir, false);
        await archive.finalize();

        const buffer = Buffer.concat(chunks);
        console.log(`Zip created! Size: ${(buffer.length / 1024 / 1024).toFixed(2)} MB`);

        // Find the collection
        const SessionModel = mongoose.model('WhatsAppSession', new mongoose.Schema({
            id: String,
            session: Buffer
        }, { collection: 'whatsapp_sessions' }));

        console.log('Uploading to MongoDB collection "whatsapp_sessions"...');
        await SessionModel.findOneAndUpdate(
            { id: clientId },
            { session: buffer },
            { upsert: true, new: true }
        );

        console.log('✅ SUCCESS: Session manually pushed to MongoDB!');
        process.exit(0);

    } catch (err) {
        console.error('❌ Failed to sync:', err);
        process.exit(1);
    }
}

forceSync();
