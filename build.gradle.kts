plugins {
    // see https://fabricmc.net/develop/ for new versions
    id("net.fabricmc.fabric-loom") version "1.15-SNAPSHOT" apply false
    // see https://projects.neoforged.net/neoforged/moddevgradle for new versions
    id("net.neoforged.moddev") version "2.0.141" apply false
    id("com.modrinth.minotaur") version "2.+" apply false
    id("net.darkhax.curseforgegradle") version "1.1.24" apply false
}

tasks.register("publishLoaderReleases") {
    group = "publishing"
    description = "Publish Fabric and NeoForge artifacts to configured platforms."
    dependsOn(":fabric:publishToPlatformServices", ":neoforge:publishToPlatformServices")
}

