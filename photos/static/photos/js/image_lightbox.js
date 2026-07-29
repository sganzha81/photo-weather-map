(function () {
    "use strict";

    const lightbox = document.querySelector("[data-image-lightbox]");
    if (!lightbox) {
        return;
    }

    const image = lightbox.querySelector("[data-lightbox-image-target]");
    const closeButton = lightbox.querySelector(".image-lightbox-close");
    const errorMessage = lightbox.querySelector("[data-lightbox-error]");
    let openingTrigger = null;

    function openLightbox(trigger) {
        const imageUrl = trigger.dataset.lightboxSrc;
        if (!imageUrl) {
            return;
        }

        openingTrigger = trigger;
        errorMessage.hidden = true;
        image.hidden = false;
        image.src = imageUrl;
        image.alt = trigger.dataset.lightboxAlt || "Фотография";
        lightbox.hidden = false;
        document.body.classList.add("image-lightbox-open");
        closeButton.focus();
    }

    function closeLightbox() {
        if (lightbox.hidden) {
            return;
        }

        lightbox.hidden = true;
        image.src = "";
        image.alt = "";
        image.hidden = false;
        errorMessage.hidden = true;
        document.body.classList.remove("image-lightbox-open");

        if (openingTrigger && document.contains(openingTrigger)) {
            openingTrigger.focus();
        }
        openingTrigger = null;
    }

    document.addEventListener("click", function (event) {
        const trigger = event.target.closest("[data-lightbox-src]");
        if (trigger) {
            event.preventDefault();
            openLightbox(trigger);
            return;
        }

        if (event.target.closest("[data-lightbox-close]")) {
            closeLightbox();
        }
    });

    document.addEventListener("keydown", function (event) {
        if (lightbox.hidden) {
            return;
        }

        if (event.key === "Escape") {
            event.preventDefault();
            closeLightbox();
        } else if (event.key === "Tab") {
            event.preventDefault();
            closeButton.focus();
        }
    });

    image.addEventListener("load", function () {
        errorMessage.hidden = true;
        image.hidden = false;
    });

    image.addEventListener("error", function () {
        image.hidden = true;
        errorMessage.hidden = false;
    });
})();
