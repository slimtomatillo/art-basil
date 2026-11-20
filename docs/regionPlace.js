// Under a region page's title: "Oregon, USA". Fills every <... data-region-place="pdx"> from
// docs/data/region_info.json, so the place is written once, in that file.
(function () {
    const targets = document.querySelectorAll('[data-region-place]');
    if (!targets.length || typeof RegionInfo === 'undefined') return;
    RegionInfo.load('../data/region_info.json')
        .then(info => {
            targets.forEach(target => {
                const region = info[target.dataset.regionPlace];
                if (region) target.textContent = RegionInfo.placeLine(region);
            });
        })
        .catch(() => { /* the title already names the region; the place line stays empty */ });
}());
