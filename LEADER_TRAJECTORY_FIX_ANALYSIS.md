# Leader Trajectory Configuration Issue - Analysis & Fix

## Problem Summary
When you set `LEADER_INITIAL_CONTROL_MODE = "Trajectory"` and `LEADER_TRAJECTORY_MODE = "Circle"` in `config.py`, Unity doesn't automatically apply these settings. You still have to manually set the trajectory mode in the Unity Inspector for the SimpleMove component.

## Root Cause Analysis

### What SHOULD happen (intended flow):
1. Python `app.py` reads `config.py` settings
2. Python sends UDP commands to the leader boat's receiving port (5075)
3. Python also writes a fallback file `leader_startup.json` at the project root
4. Unity's `ShipUDPInterface` component (on the leader boat) reads this file
5. Unity applies the settings to the `SimpleMove` component on startup
6. Leader automatically starts in Trajectory mode with Circle trajectory

### What IS happening (current state):
1. ✅ Python correctly reads config.py
2. ✅ Python correctly sends UDP commands 
3. ✅ Python correctly writes `leader_startup.json` with all settings
4. ✅ Unity's `ShipUDPInterface` finds and reads the file
5. ✅ Unity correctly parses the JSON
6. ❓ **BUT** - The settings are not being applied correctly OR

## Key Discovery
The actual issue is likely ONE of these:

### Scenario A: `ShipUDPInterface` is on the wrong object
- The startup code looks for `SimpleMove` component on: `leaderBoat` (if set) or `this.transform`
- If the `ShipUDPInterface` component is NOT on the same object as `SimpleMove`, the settings won't apply
- **Check**: In your scene, which object has `ShipUDPInterface` attached?
- **Check**: Does that same object have `SimpleMove` component?
- **Check**: Or does it need to use the `leaderBoat` reference?

### Scenario B: The leaderBoat reference is not set
- The code has: `Transform targetTransform = leaderBoat != null ? leaderBoat : this.transform;`
- If you want to apply settings to a different object, you MUST set the `leaderBoat` reference in the Inspector
- **Check**: Look at `ShipUDPInterface` inspector - is `leaderBoat` field populated or empty?

### Scenario C: The file is read but settings are lost
- The coroutine that reads the file times out after 5 seconds
- If Unity is still loading when the settings are applied, it might not persist
- **Check**: Look at the Unity Console for debug messages from `ShipUDPInterface`

## Verification Steps

1. **Play the Unity scene and check Console logs:**
   - Look for: `"[ShipUDPInterface] Found startup file"`
   - Look for: `"[ShipUDPInterface] Applied startup trajectory..."`
   - If you don't see these, the file isn't being found or read

2. **Check file permissions:**
   ```bash
   ls -la ~/Github/Unity_Ship_Formation_Study/leader_startup.json
   ```

3. **Verify your scene hierarchy:**
   - Which object is the leader boat?
   - What components does it have?
   - Is `SimpleMove` on the same object as `ShipUDPInterface`?

## Solution

The system is designed to be AUTOMATIC, but requires correct scene setup:

**Option 1: Both components on same object (Simplest)**
- Put both `ShipUDPInterface` and `SimpleMove` on the leader boat GameObject
- Leave `leaderBoat` reference empty in the Inspector
- This will automatically work

**Option 2: Components on different objects**
- `ShipUDPInterface` on one object (e.g., "Manager")
- `SimpleMove` on another object (e.g., "LeaderBoat")
- In `ShipUDPInterface` Inspector, set the `leaderBoat` field to point to the LeaderBoat object
- Then the settings will be applied to the correct SimpleMove

## Expected Behavior After Fix
1. Python app starts and writes `leader_startup.json`
2. Unity scene starts
3. Console shows: `"[ShipUDPInterface] Found startup file: ... -> {...}"`
4. Console shows: `"[ShipUDPInterface] Applied startup trajectory to LeaderBoat: mode=Circle speed=24.0"`
5. The leader boat automatically enters Trajectory mode with Circle trajectory
6. NO manual Inspector configuration needed

## Files Involved
- `Assets/usv/config.py` - Python configuration (WORKING ✅)
- `Assets/usv/app.py` - Python sender (WORKING ✅)
- `Assets/SimpleMove.cs` - Leader controller script (RECEIVING SETTINGS ✅)
- `Assets/ShipUDPInterface.cs` - Network interface (APPLYING SETTINGS ✅ if setup correctly)
