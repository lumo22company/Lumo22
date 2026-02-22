# Caption PDF format fix – deploy required

The caption PDF now uses the **vertical table layout** (Platform | Caption | Hashtags per caption). If you're still seeing the old format in delivered captions, the live app is running old code.

## Fix: deploy the latest code

1. **Push your changes to Git** (if Railway builds from GitHub):
   ```bash
   git add -A
   git commit -m "Use vertical table layout for caption PDFs"
   git push
   ```
   Then trigger a redeploy in the Railway dashboard.

2. **Or deploy directly with Railway CLI** (uses your local folder):
   ```bash
   railway up
   ```

## Verify the fix

- Run the test script locally – it now sends PDF (same as live delivery):
  ```bash
  python3 test_captions_delivery.py your@email.com
  ```
- Check the attached PDF – it should show the vertical layout (Platform/Caption/Hashtags rows per caption).
- After deploying, trigger a new caption delivery (new intake or deliver-test) to confirm.
