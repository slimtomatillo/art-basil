class CursorTrail {
    constructor() {
        this.dots = [];
        this.maxDots = 35;
        this.lastCall = 0;
        this.throttleTime = 16;
        this.hue = 0;
        
        document.addEventListener('mousemove', (e) => this.handleMouseMove(e));
    }

    handleMouseMove(e) {
        const now = Date.now();
        if (now - this.lastCall < this.throttleTime) return;
        this.lastCall = now;

        const dot = document.createElement('div');
        dot.className = 'cursor-trail';
        dot.style.left = `${e.pageX}px`;
        dot.style.top = `${e.pageY}px`;
        
        dot.style.backgroundColor = `hsla(${this.hue}, 100%, 50%, 0.3)`;
        dot.style.boxShadow = `0 0 5px 2px hsla(${this.hue}, 100%, 50%, 0.2)`;
        
        this.hue = (this.hue + 10) % 360;

        document.body.appendChild(dot);
        this.dots.push(dot);

        setTimeout(() => {
            dot.style.opacity = '0';
        }, 800);

        setTimeout(() => {
            if (dot.parentElement) {
                document.body.removeChild(dot);
                this.dots = this.dots.filter(d => d !== dot);
            }
        }, 3000);

        while (this.dots.length > this.maxDots) {
            const oldDot = this.dots.shift();
            if (oldDot.parentElement) {
                document.body.removeChild(oldDot);
            }
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new CursorTrail();
}); 