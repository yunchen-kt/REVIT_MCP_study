import { RevitSocketClient } from '../build/socket.js';

async function checkFARCompliance() {
    const client = new RevitSocketClient('localhost', 8966);

    // User Inputs
    const SITE_AREA = 500.0; // m²
    const MAX_FAR_PERCENT = 225.0; // %

    try {
        console.log('🔌 Connecting to Revit...');
        await client.connect();

        // 1. Get Levels and Rooms to calculate Total Effective Area
        const levelsRes = await client.sendCommand('get_all_levels', {});
        if (!levelsRes.success) throw new Error(levelsRes.error);
        const levels = levelsRes.data.Levels;

        // Rules (Same as before)
        const rules = [
            { type: 'Stair', keywords: ['樓梯', 'Stair'], factor: 0.0 },
            { type: 'Balcony', keywords: ['陽台', 'Balcony', '露台', 'Terrace'], factor: 0.5 },
            { type: 'Main', keywords: [], factor: 1.0 }
        ];

        let grandTotalEffectiveArea = 0;

        // Calculate Area
        for (const level of levels) {
            const roomRes = await client.sendCommand('get_rooms_by_level', { level: level.Name });
            if (!roomRes.success || !roomRes.data.Rooms) continue;

            const rooms = roomRes.data.Rooms;
            let levelEffectiveArea = 0;

            rooms.forEach(room => {
                let factor = 1.0;
                // Check Stair
                if (rules[0].keywords.some(k => room.Name.includes(k))) {
                    factor = rules[0].factor;
                }
                // Check Balcony
                else if (rules[1].keywords.some(k => room.Name.includes(k))) {
                    factor = rules[1].factor;
                }
                levelEffectiveArea += (room.Area * factor);
            });
            grandTotalEffectiveArea += levelEffectiveArea;
        }

        // 2. Perform Compliance Check
        const maxAllowedArea = SITE_AREA * (MAX_FAR_PERCENT / 100);
        const currentFAR = (grandTotalEffectiveArea / SITE_AREA) * 100;
        const isCompliant = grandTotalEffectiveArea <= maxAllowedArea;
        const remainingArea = maxAllowedArea - grandTotalEffectiveArea;

        // 3. Output Report
        console.log('\n⚖️  FAR Compliance Check Report (容積率檢討)');
        console.log('==================================================');
        console.log(`📌 Site Parameters (基地設定):`);
        console.log(`   - Site Area (基地面積):     ${SITE_AREA.toFixed(2)} m²`);
        console.log(`   - Max FAR (法定容積率):     ${MAX_FAR_PERCENT.toFixed(2)} %`);
        console.log(`   - Max Floor Area (容積上限): ${maxAllowedArea.toFixed(2)} m²`);
        console.log('\n🏢 Current Design (目前設計):');
        console.log(`   - Total Effective Area:   ${grandTotalEffectiveArea.toFixed(2)} m²`);
        console.log(`   - Current FAR (設計容積率): ${currentFAR.toFixed(2)} %`);
        console.log('--------------------------------------------------');

        if (isCompliant) {
            console.log('✅ RESULT: PASS (符合規定)');
            console.log(`🎉 You have ${remainingArea.toFixed(2)} m² remaining area allowance.`);
        } else {
            console.log('❌ RESULT: FAIL (不符合規定)');
            console.log(`⚠️  Exceeded by ${Math.abs(remainingArea).toFixed(2)} m²!`);
        }
        console.log('==================================================');

    } catch (error) {
        console.error('❌ Error:', error);
    } finally {
        client.disconnect();
    }
}

checkFARCompliance();
