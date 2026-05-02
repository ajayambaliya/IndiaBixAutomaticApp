const mongoose = require('mongoose');
const path = require('path');
require('dotenv').config({ path: path.join(__dirname, '../.env') });
require('dotenv').config();

async function test() {
    const uri = process.env.MONGO_DB_URI;
    if (!uri) {
        console.error('❌ Error: MONGO_DB_URI is missing in .env');
        return;
    }
    
    console.log('Testing connection to MongoDB...');
    
    try {
        await mongoose.connect(uri, {
            useNewUrlParser: true,
            useUnifiedTopology: true,
        });
        console.log('✅ SUCCESS: Connected to MongoDB!');
        
        // List collections in the current DB
        const collections = await mongoose.connection.db.listCollections().toArray();
        console.log('Existing Collections:', collections.map(c => c.name).join(', ') || '(none)');
        
        await mongoose.disconnect();
        console.log('Disconnected successfully.');
    } catch (err) {
        console.error('❌ FAILED: Could not connect to MongoDB.');
        console.error('Error details:', err.message);
        process.exit(1);
    }
}

test();
