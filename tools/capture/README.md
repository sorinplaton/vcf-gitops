# Headed-browser captures

Takes screenshots with a real (non-headless) Chromium on a virtual X screen, so the
browser frame and the address bar are in the picture. Used for the captures of the
blog post "Six VMs from one commit". Read-only: it opens pages and photographs them.

## One-time setup (Ubuntu)

    sudo apt-get install -y xvfb fluxbox scrot xdotool imagemagick nodejs npm
    npm install                      # installs playwright from package.json
    npx playwright install chromium  # add --with-deps if system libraries are missing

## Start the virtual screen

    ./screen.sh start     # Xvfb :99 at 1680x1000x24, then fluxbox on DISPLAY=:99
    ./screen.sh status
    ./screen.sh stop

What `screen.sh start` runs:

    Xvfb :99 -screen 0 1680x1000x24 -nolisten tcp &
    DISPLAY=:99 fluxbox -rc ./fluxbox-init &

`fluxbox-init` and `fluxbox-apps` are written by the script: no toolbar, no window
decorations, every window maximized, so the browser owns the whole 1680x1000 screen.

## Take a capture

    node shot.js <name> <url> [step ...]

Saves `~/captures/<name>.png` (whole screen through `scrot`, address bar included) and
`~/captures/<name>-page.png` (Playwright page screenshot, content only). Every step is
logged with a timestamp to `shot.log` next to the script.

Steps, run in order after the page has loaded:

| Step | Effect |
|---|---|
| `login:argocd` | log in to Argo CD as `admin` (or `$ARGOCD_USER`) with `$ARGOCD_PASSWORD`, then reopen the URL |
| `login:vcenter` | log in to the vSphere Client with `$VC_USER` / `$VC_PASSWORD`, then reopen the URL |
| `click:<selector>` | click the first element matching a Playwright selector |
| `try-click:<selector>` | click it if it is there within 3 s (a dismissible banner); never fails |
| `hover:<selector>` | put the mouse on the first matching element and leave it there |
| `wait:<text>` | wait until the text is visible |
| `expect:<text>` | require the text to be visible and log the element's full text; the capture fails otherwise |
| `reload-until-not:<text>` | reload, at most 10 times, until the text is no longer shown |
| `sleep:<ms>` | pause |

Passwords are read from the environment only. They are never written to a file or to the
log, and password fields are emptied before any screenshot. On a failed step the script
saves `<name>-diag.png` and exits with code 1; a missing variable exits with code 2.

## Examples

    export ARGOCD_PASSWORD=...   # in the shell, not in a file

    node shot.js s12-podinfo-app-hover \
      'https://10.200.200.5/applications/argocd-demo-wqfbg/podinfo-vks?view=network' \
      login:argocd 'wait:podinfo-5448f4f4fb' \
      'hover:.application-resource-tree__node:has-text("podinfo-5448f4f4fb-4vh67") >> text=more' \
      sleep:1200 'expect:demo-vks-cluster-node-pool-1'

    node shot.js s13-podinfo-browser-urlbar http://10.200.200.8:9898 \
      'wait:greetings from podinfo' 'wait:Served by' \
      'reload-until-not:podinfo-5448f4f4fb-vltgc' 'wait:6.15.0'

    node shot.js s16b-argocd-podinfo-helm \
      'https://10.200.200.5/applications/argocd-demo-wqfbg/podinfo?view=tree' \
      login:argocd 'wait:podinfo' sleep:2500

    export VC_USER=... VC_PASSWORD=...

    node shot.js s16a-vsphere-pods \
      'https://vc-wld01-a.site-a.vcf.lab/ui/app/workload-platform;nav=v/namespace/urn:vapi:com.vmware.wcp.WorkloadModel:podinfo-demo-vkjhr:cc745437-7983-429a-b5cd-4a03d6d2ad18/compute/pods' \
      login:vcenter 'wait:podinfo-69547cd6b7' sleep:3000 \
      'try-click:clr-alert button.close' sleep:800 'try-click:clr-alert button.close' sleep:1500 \
      'expect:podinfo-69547cd6b7-529fn'

    convert s16a-vsphere-pods.png s16b-argocd-podinfo-helm.png +append s16-vsphere-pods.png

## Notes

- Chromium is launched with `headless: false`, `ignoreDefaultArgs: ['--enable-automation']`
  and `--test-type`, so neither the "controlled by automated test software" bar nor the
  "unsupported command-line flag" bar is drawn. Certificate errors are ignored
  (`ignoreHTTPSErrors: true`); the address bar then shows "Not secure".
- The target is opened with `window.open` from a blank tab. A tab opened that way has the
  focus on the page, so the URL in the address bar is not highlighted.
- In the Argo CD Network view the node name of a Pod is in the popover of its "more" tag,
  not in the tooltip of the Pod box.
- In the vSphere Client the vSphere Pods of a namespace are under Workload Management >
  namespace > Compute > Core Kubernetes > Pods (column "vSphere Pod").
