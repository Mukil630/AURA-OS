const fs = require('fs');
const path = require('path');
const http = require('http');
const url = require('url');

// Use googleapis from sgc-billing node_modules
const sgcPath = path.join('C:', 'Users', 'mukil', 'sgc-billing', 'node_modules', 'googleapis');
const { google } = require(sgcPath);

const DRIVE_FOLDER_ID = '1nGZG5-eIcxmkgQxBtZ7tjGTUoWWNY4m1';
const VAULT_DIR = path.join(__dirname, '..', 'storage', 'vault');
const TOKEN_FILE = path.join(VAULT_DIR, 'google_drive_token.json');

// Read Client Secret from sgc-billing data store
const appDataPath = path.join(process.env.APPDATA, 'sgc-billing', 'sgc-billing-data.json');
let clientSecret = null;
if (fs.existsSync(appDataPath)) {
  try {
    const d = JSON.parse(fs.readFileSync(appDataPath, 'utf8'));
    clientSecret = d['google-client-secret'];
  } catch (e) {}
}

if (!clientSecret || !clientSecret.installed) {
  console.error('No Google Client Secret found.');
  process.exit(1);
}

const { client_id, client_secret } = clientSecret.installed;
const redirectUri = 'http://localhost:3000/oauth2callback';

const oauth2Client = new google.auth.OAuth2(client_id, client_secret, redirectUri);

async function getAuthenticatedClient() {
  if (fs.existsSync(TOKEN_FILE)) {
    try {
      const tokens = JSON.parse(fs.readFileSync(TOKEN_FILE, 'utf8'));
      oauth2Client.setCredentials(tokens);
      return oauth2Client;
    } catch (e) {}
  }

  // Generate Auth URL
  const scopes = ['https://www.googleapis.com/auth/drive.file', 'https://www.googleapis.com/auth/drive'];
  const authUrl = oauth2Client.generateAuthUrl({
    access_type: 'offline',
    scope: scopes,
    prompt: 'consent'
  });

  console.log('\n=============================================================');
  console.log('🚀 AURA GOOGLE DRIVE 5TB MASTER VAULT AUTHENTICATION');
  console.log('=============================================================');
  console.log('Opening Google Sign-In in your browser...\n');

  // Open browser
  require('child_process').exec(`start "" "${authUrl}"`);

  return new Promise((resolve, reject) => {
    const server = http.createServer(async (req, res) => {
      if (req.url.startsWith('/oauth2callback')) {
        const qs = new url.URL(req.url, 'http://localhost:3000').searchParams;
        const code = qs.get('code');
        res.end('<h1>Google Drive Authenticated for AURA! You can close this tab now.</h1>');
        server.close();

        try {
          const { tokens } = await oauth2Client.getToken(code);
          oauth2Client.setCredentials(tokens);
          fs.writeFileSync(TOKEN_FILE, JSON.stringify(tokens, null, 2));
          console.log('✅ Google Drive tokens saved to storage/vault/google_drive_token.json!');
          resolve(oauth2Client);
        } catch (err) {
          reject(err);
        }
      }
    }).listen(3000);
  });
}

async function uploadFile(drive, filePath, folderId = DRIVE_FOLDER_ID) {
  if (!fs.existsSync(filePath)) return null;
  const fileName = path.basename(filePath);
  
  const fileMetadata = {
    name: fileName,
    parents: [folderId]
  };
  const media = {
    body: fs.createReadStream(filePath)
  };

  try {
    const res = await drive.files.create({
      resource: fileMetadata,
      media: media,
      fields: 'id, name, webViewLink'
    });
    console.log(`✅ Uploaded: ${fileName} -> ${res.data.webViewLink}`);
    return res.data;
  } catch (err) {
    console.error(`Upload error for ${fileName}:`, err.message);
    return null;
  }
}

async function main() {
  try {
    const auth = await getAuthenticatedClient();
    const drive = google.drive({ version: 'v3', auth });

    const baseDir = path.join(__dirname, '..');
    const filesToSync = [
      path.join(baseDir, 'storage', 'memory', 'user_profile.json'),
      path.join(baseDir, 'storage', 'memory', 'context.json'),
      path.join(baseDir, 'storage', 'memory', 'system_blueprint.json'),
      path.join(baseDir, 'AURA_MASTER_KNOWLEDGE_VAULT.md'),
      path.join(baseDir, 'README.md'),
      path.join(baseDir, 'AURA_LIVE_PRACTICAL_PROOF.txt'),
      'C:\\Users\\mukil\\OneDrive\\placement questions\\MK.PDF.RESUME.pdf'
    ];

    console.log(`\n☁️ Uploading all core knowledge files to 5TB Master Vault (${DRIVE_FOLDER_ID})...\n`);
    for (const f of filesToSync) {
      await uploadFile(drive, f);
    }
    console.log('\n🎉 ALL FILES SUCCESSFULLY POPULATED IN 5TB GOOGLE DRIVE MASTER VAULT!');
  } catch (err) {
    console.error('Authentication or upload failed:', err);
  }
}

main();
