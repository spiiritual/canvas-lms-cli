# canvas-lms-cli
A CLI-based client for Canvas LMS, designed for easy human and agent use.

Right now it can:
 - [x] Log into Canvas
 - [x] List enrolled classes at a glance (name, id, current grade)
 - [ ] List class information (teachers, TAs, announcements, etc.)
 - [ ] List assignments within classes
 - [ ] List assignments with upcoming due dates
 - [ ] Submit assignments 

## Authentication
Unlike other Canvas clients that use access keys generated on the Canvas website, canvas-lms-cli uses the QR for Mobile Login feature to log into Canvas. Generate a QR code, and paste the link from the QR code like this:

    canvas-lms-cli authenticate --link <LINK>
    
Why use QR codes instead of access tokens? It's because my university has disabled generating access tokens, so I have to do it like this instead. In practice, it works the exact same way as generating an access token.